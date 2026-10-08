//! Finite observed queue identities and PI request/dispatch scopes.
//! This replays slot witnesses, not hardware timing or complete heap state.
use crate::{
    fetch, history,
    pi_history::{self, PiHistoryReport, PiRecord},
    program::*,
    rom::CanonicalRom,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    io::{self, BufRead, Read, Seek},
};

pub const FORMAT: &str = "plaid-ares-access-history-v2";
pub const POLICY: &str = "identity_ram_buffered_pi_and_actual_queue_scopes";
pub const MAX_IDENTITIES: u64 = 1_000_000;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RequestStatusLink {
    pub event: u32,
    pub token: u64,
    pub request: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PiQueueHistoryReport {
    pub format: String,
    pub scope: String,
    pub history_sha256: String,
    pub projection: PiHistoryReport,
    pub records: u64,
    #[serde(with = "crate::program::unique_map")]
    pub event_counts: BTreeMap<String, u64>,
    pub accepted_requests: u64,
    pub successful_insertions: u64,
    pub rejected_requests: u64,
    pub request_status_links: Vec<RequestStatusLink>,
    pub unknown_statuses: u64,
    pub requests_without_status: Vec<u64>,
    pub guest_completion_claimed: bool,
    pub native_complete: bool,
}

#[derive(Debug, Deserialize)]
#[serde(untagged)]
enum Wire {
    Schedule(Schedule),
    Legacy(pi_history::Wire),
}

#[derive(Debug, Deserialize)]
#[serde(tag = "record", rename_all = "snake_case", deny_unknown_fields)]
enum Schedule {
    Queue {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        kind: u32,
        slot: u32,
        other: u32,
        event: u32,
        clock: u32,
        valid: bool,
        token: u64,
        request: u64,
        active_request: u64,
    },
    PiRequestBegin {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        request: u64,
        direction: u32,
        token: u64,
        dram: PhysicalAddr,
        pbus: PhysicalAddr,
        length: u32,
    },
    PiRequestEnd {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        request: u64,
        direction: u32,
        token: u64,
        dram: PhysicalAddr,
        pbus: PhysicalAddr,
        length: u32,
    },
    DispatchBegin {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        event: u32,
        token: u64,
        request: u64,
    },
    DispatchEnd {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        event: u32,
        token: u64,
        request: u64,
    },
    PiCopyRequest {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        transfer: u64,
        request: u64,
        token: u64,
    },
    PiStatusScope {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        dispatch: bool,
        event: u32,
        token: u64,
        request: u64,
    },
}
impl Schedule {
    fn identity(&self) -> (u64, u64, GuestVirtualAddr, &'static str) {
        let (ordinal, context, pc, name) = match self {
            Self::Queue {
                ordinal,
                context,
                pc,
                ..
            } => (*ordinal, *context, *pc, "queue"),
            Self::PiRequestBegin {
                ordinal,
                context,
                pc,
                ..
            } => (*ordinal, *context, *pc, "pi_request_begin"),
            Self::PiRequestEnd {
                ordinal,
                context,
                pc,
                ..
            } => (*ordinal, *context, *pc, "pi_request_end"),
            Self::DispatchBegin {
                ordinal,
                context,
                pc,
                ..
            } => (*ordinal, *context, *pc, "dispatch_begin"),
            Self::DispatchEnd {
                ordinal,
                context,
                pc,
                ..
            } => (*ordinal, *context, *pc, "dispatch_end"),
            Self::PiCopyRequest {
                ordinal,
                context,
                pc,
                ..
            } => (*ordinal, *context, *pc, "pi_copy_request"),
            Self::PiStatusScope {
                ordinal,
                context,
                pc,
                ..
            } => (*ordinal, *context, *pc, "pi_status_scope"),
        };
        (ordinal, context, pc, name)
    }
}
struct Request {
    direction: u32,
    dram: PhysicalAddr,
    pbus: PhysicalAddr,
    length: u32,
    pc: GuestVirtualAddr,
    token: u64,
    outcome: Option<bool>,
    returned: bool,
    transfer: Option<u64>,
    status: bool,
}
struct Token {
    event: u32,
    clock: u32,
    valid: bool,
    request: u64,
    removed: bool,
}
#[derive(Clone, Copy, PartialEq, Eq)]
struct Dispatch {
    event: u32,
    token: u64,
    request: u64,
    pc: GuestVirtualAddr,
}
struct ActiveDispatch {
    identity: Dispatch,
    statuses: u32,
}
struct CopyJoin {
    transfer: u64,
    request: u64,
}
struct Projection<H> {
    input: H,
    raw: Vec<u8>,
    output: Vec<u8>,
    position: usize,
    hash: Sha256,
    header: bool,
    ended: bool,
    records: u64,
    projected: u64,
    counts: BTreeMap<String, u64>,
    active_fetch: Option<(u64, u64, GuestVirtualAddr)>,
    pending_fetch: Option<(u64, u64)>,
    slots: [u64; 512],
    tokens: BTreeMap<u64, Token>,
    next_token: u64,
    requests: Vec<Request>,
    current: Option<u64>,
    removal: Option<Dispatch>,
    dispatch: Option<ActiveDispatch>,
    copy_join: Option<CopyJoin>,
    status_join: Option<Dispatch>,
    copying: bool,
    statuses: Vec<RequestStatusLink>,
    unknown: u64,
}
fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}
impl<H: BufRead> Projection<H> {
    fn new(input: H) -> Self {
        Self {
            input,
            raw: Vec::new(),
            output: Vec::new(),
            position: 0,
            hash: Sha256::new(),
            header: false,
            ended: false,
            records: 0,
            projected: 0,
            counts: BTreeMap::new(),
            active_fetch: None,
            pending_fetch: None,
            slots: [0; 512],
            tokens: BTreeMap::new(),
            next_token: 0,
            requests: Vec::new(),
            current: None,
            removal: None,
            dispatch: None,
            copy_join: None,
            status_join: None,
            copying: false,
            statuses: Vec::new(),
            unknown: 0,
        }
    }
    fn request(&self, id: u64) -> Result<&Request, String> {
        self.requests
            .get(id.checked_sub(1).ok_or("zero request identity")? as usize)
            .ok_or_else(|| "unknown request identity".into())
    }
    fn request_mut(&mut self, id: u64) -> Result<&mut Request, String> {
        self.requests
            .get_mut(id.checked_sub(1).ok_or("zero request identity")? as usize)
            .ok_or_else(|| "unknown request identity".into())
    }
    fn identity(&mut self, ordinal: u64, kind: &str) -> Result<(), String> {
        require(
            self.header && self.records < history::MAX_RECORDS,
            "missing v2 header or record bound exceeded",
        )?;
        self.records += 1;
        require(ordinal == self.records, "v2 ordinal is not contiguous")?;
        *self.counts.entry(kind.into()).or_default() += 1;
        Ok(())
    }
    fn schedule(&mut self, s: Schedule) -> Result<(), String> {
        let (ordinal, context, pc, name) = s.identity();
        self.identity(ordinal, name)?;
        require(
            context == 0
                && self.active_fetch.is_none()
                && self.pending_fetch.is_none()
                && !self.copying,
            "scheduling record inside fetch or buffered copy",
        )?;
        require(
            self.copy_join.is_none() && self.status_join.is_none(),
            "interposed scheduling join",
        )?;
        require(
            self.removal.is_none()
                || matches!(
                    s,
                    Schedule::DispatchBegin { .. } | Schedule::Queue { kind: 6 | 7, .. }
                ),
            "stale valid removal",
        )?;
        match s {
            Schedule::PiRequestBegin {
                request,
                direction,
                token,
                dram,
                pbus,
                length,
                ..
            } => {
                require(
                    self.current.is_none()
                        && self.dispatch.is_none()
                        && request == self.requests.len() as u64 + 1
                        && request <= MAX_IDENTITIES
                        && token == 0
                        && direction <= 1
                        && dram.0 < 0x1000000
                        && length > 0
                        && length <= 0x1000000,
                    "invalid accepted request begin",
                )?;
                self.requests.push(Request {
                    direction,
                    dram,
                    pbus,
                    length,
                    pc,
                    token: 0,
                    outcome: None,
                    returned: false,
                    transfer: None,
                    status: false,
                });
                self.current = Some(request);
            }
            Schedule::PiRequestEnd {
                request,
                direction,
                token,
                dram,
                pbus,
                length,
                ..
            } => {
                require(
                    self.current == Some(request),
                    "request end without current begin",
                )?;
                let r = self.request_mut(request)?;
                require(
                    (direction, token, dram, pbus, length, pc)
                        == (r.direction, r.token, r.dram, r.pbus, r.length, r.pc)
                        && r.outcome.is_some()
                        && (direction == 0 || r.transfer.is_some()),
                    "request return disagrees with accepted snapshot/outcome",
                )?;
                r.returned = true;
                self.current = None;
            }
            Schedule::Queue {
                kind,
                slot,
                other,
                event,
                clock,
                valid,
                token,
                request,
                active_request,
                ..
            } => {
                require(
                    (1..=9).contains(&kind) && active_request == self.current.unwrap_or(0),
                    "invalid queue kind/active request",
                )?;
                require(
                    kind != 9 || !valid,
                    "host restore violates declared boot lifecycle",
                )?;
                let observed = match kind {
                    1 | 9 => {
                        require(
                            slot == 0 && other == 0 && event == 0 && clock == 0 && !valid,
                            "noncanonical reset/save witness",
                        )?;
                        if kind == 1 {
                            self.slots.fill(0);
                            self.tokens.clear();
                        }
                        0
                    }
                    2 => {
                        require(
                            slot == 512 && other == 0 && !valid,
                            "invalid rejected insertion",
                        )?;
                        0
                    }
                    3 | 6 | 7 => {
                        require(
                            slot < 512 && other < 512,
                            "queue move outside observed slots",
                        )?;
                        let id = self.slots[other as usize];
                        if id != 0 {
                            let t = self.tokens.get(&id).ok_or("missing moved token")?;
                            require(
                                (event, clock, valid) == (t.event, t.clock, t.valid),
                                "moved token metadata changed",
                            )?;
                        }
                        self.slots[slot as usize] = id;
                        id
                    }
                    4 => {
                        require(
                            slot < 512 && other == 0 && valid && self.next_token < MAX_IDENTITIES,
                            "invalid successful insertion",
                        )?;
                        self.next_token += 1;
                        let owner = if let Some(id) = self.current {
                            if self.request(id)?.direction == event {
                                id
                            } else {
                                0
                            }
                        } else {
                            0
                        };
                        self.tokens.insert(
                            self.next_token,
                            Token {
                                event,
                                clock,
                                valid,
                                request: owner,
                                removed: false,
                            },
                        );
                        self.slots[slot as usize] = self.next_token;
                        self.next_token
                    }
                    5 | 8 => {
                        require(
                            slot < 512
                                && if kind == 5 {
                                    slot == 0 && other < 512
                                } else {
                                    other == 0
                                },
                            "invalid removal/cancel slot",
                        )?;
                        let id = self.slots[slot as usize];
                        if id != 0 {
                            let t = self.tokens.get_mut(&id).ok_or("missing removed token")?;
                            require(
                                !t.removed && (event, clock, valid) == (t.event, t.clock, t.valid),
                                "reused/changed removal identity",
                            )?;
                            if kind == 8 {
                                t.valid = false;
                            } else {
                                t.removed = true;
                            }
                        }
                        if kind == 5 && valid {
                            self.removal = Some(Dispatch {
                                event,
                                token: id,
                                request: self.tokens.get(&id).map_or(0, |t| t.request),
                                pc,
                            });
                        }
                        id
                    }
                    _ => unreachable!(),
                };
                require(
                    token == observed
                        && request == self.tokens.get(&observed).map_or(0, |t| t.request),
                    "queue identity annotation mismatch",
                )?;
                if matches!(kind, 2 | 4)
                    && let Some(id) = self.current
                {
                    let r = self.request_mut(id)?;
                    if r.direction == event {
                        require(
                            r.pc == pc && r.outcome.is_none(),
                            "duplicate/misplaced request insertion outcome",
                        )?;
                        r.outcome = Some(kind == 4);
                        r.token = token;
                    }
                }
            }
            Schedule::DispatchBegin {
                event,
                token,
                request,
                ..
            } => {
                let identity = Dispatch {
                    event,
                    token,
                    request,
                    pc,
                };
                require(
                    self.current.is_none()
                        && self.dispatch.is_none()
                        && self.removal == Some(identity),
                    "dispatch lacks immediate actual valid removal",
                )?;
                if request != 0 {
                    let r = self.request(request)?;
                    require(
                        r.returned && r.direction == event,
                        "dispatch precedes request return or changes direction",
                    )?;
                }
                self.removal = None;
                self.dispatch = Some(ActiveDispatch {
                    identity,
                    statuses: 0,
                });
            }
            Schedule::DispatchEnd {
                event,
                token,
                request,
                ..
            } => {
                let d = self.dispatch.take().ok_or("dispatch end without begin")?;
                require(
                    d.identity
                        == Dispatch {
                            event,
                            token,
                            request,
                            pc,
                        }
                        && d.statuses == u32::from(event <= 1),
                    "dispatch return/status mismatch",
                )?;
            }
            Schedule::PiCopyRequest {
                transfer,
                request,
                token,
                ..
            } => {
                require(
                    self.current == Some(request) && transfer > 0,
                    "copy binding outside request",
                )?;
                let r = self.request_mut(request)?;
                require(
                    r.direction == 1
                        && r.outcome.is_some()
                        && r.transfer.is_none()
                        && r.pc == pc
                        && r.token == token,
                    "copy binding disagrees with request",
                )?;
                r.transfer = Some(transfer);
                self.copy_join = Some(CopyJoin { transfer, request });
            }
            Schedule::PiStatusScope {
                dispatch,
                event,
                token,
                request,
                ..
            } => {
                require(
                    dispatch == self.dispatch.is_some(),
                    "status dispatch annotation mismatch",
                )?;
                if let Some(d) = &mut self.dispatch {
                    require(
                        event <= 1
                            && d.identity
                                == Dispatch {
                                    event,
                                    token,
                                    request,
                                    pc,
                                }
                            && d.statuses == 0,
                        "status scope does not match actual dispatch",
                    )?;
                    d.statuses += 1;
                } else {
                    require(
                        event == 0 && token == 0 && request == 0,
                        "direct status invents request identity",
                    )?;
                }
                self.status_join = Some(Dispatch {
                    event,
                    token,
                    request,
                    pc,
                });
            }
        }
        Ok(())
    }
    fn legacy(&mut self, mut record: pi_history::Wire) -> Result<(), String> {
        use history::Record as R;
        match &mut record {
            pi_history::Wire::Base(R::Header {
                format,
                policy,
                lifecycle_policy,
                ..
            }) => {
                require(
                    !self.header
                        && format == FORMAT
                        && policy == POLICY
                        && lifecycle_policy == history::LIFECYCLE_POLICY,
                    "unsupported/repeated v2 header",
                )?;
                self.header = true;
                *format = pi_history::FORMAT.into();
                *policy = pi_history::POLICY.into();
            }
            pi_history::Wire::Base(R::End { record_count, .. }) => {
                require(
                    self.header
                        && *record_count == self.records
                        && self.current.is_none()
                        && self.removal.is_none()
                        && self.dispatch.is_none()
                        && self.copy_join.is_none()
                        && self.status_join.is_none()
                        && !self.copying
                        && self.active_fetch.is_none()
                        && self.pending_fetch.is_none(),
                    "incomplete v2 footer",
                )?;
                *record_count = self.projected;
                self.ended = true;
            }
            _ => {
                let (ordinal, context, pc, kind) =
                    record.identity().ok_or("missing legacy identity")?;
                self.identity(ordinal, kind)?;
                require(
                    self.removal.is_none(),
                    "stale valid removal before legacy record",
                )?;
                require(
                    self.copy_join.is_none()
                        || matches!(
                            record,
                            pi_history::Wire::Pi(PiRecord::PiDma { event: 1, .. })
                        ),
                    "orphan copy binding",
                )?;
                require(
                    self.status_join.is_none()
                        || matches!(
                            record,
                            pi_history::Wire::Pi(PiRecord::PiDma { event: 8, .. })
                        ),
                    "orphan status scope",
                )?;
                if let pi_history::Wire::Pi(PiRecord::PiDma {
                    event,
                    transfer,
                    dram,
                    pbus,
                    length,
                    ..
                }) = &record
                {
                    match event {
                        1 => {
                            let join = self
                                .copy_join
                                .take()
                                .ok_or("copy lacks accepted request binding")?;
                            let r = self.request(join.request)?;
                            require(
                                !self.copying
                                    && *transfer == join.transfer
                                    && (*dram, *pbus, *length, pc)
                                        == (r.dram, r.pbus, r.length, r.pc),
                                "copy start disagrees with accepted request",
                            )?;
                            self.copying = true;
                        }
                        7 => {
                            require(self.copying, "copy return without start")?;
                            self.copying = false;
                        }
                        8 => {
                            let s = self.status_join.take().ok_or("status lacks actual scope")?;
                            require(pc == s.pc, "status PC differs from scope")?;
                            if s.request == 0 {
                                self.unknown += 1;
                            } else {
                                let r = self.request_mut(s.request)?;
                                require(!r.status, "request receives repeated status")?;
                                r.status = true;
                                self.statuses.push(RequestStatusLink {
                                    event: s.event,
                                    token: s.token,
                                    request: s.request,
                                });
                            }
                        }
                        _ => {}
                    }
                }
                require(
                    self.pending_fetch.is_none() || kind == "fetch",
                    "fetch prologue must immediately follow return",
                )?;
                self.projected += 1;
                if kind == "fetch_begin" {
                    require(
                        self.active_fetch.is_none()
                            && self.pending_fetch.is_none()
                            && context == ordinal,
                        "invalid v2 fetch begin",
                    )?;
                    self.active_fetch = Some((ordinal, self.projected, pc));
                }
                require(
                    context == self.active_fetch.map_or(0, |a| a.0)
                        && self.active_fetch.is_none_or(|a| a.2 == pc),
                    "v2 raw fetch context/PC mismatch",
                )?;
                record.renumber(self.projected, self.active_fetch.map_or(0, |a| a.1));
                if kind == "fetch_end" {
                    let a = self
                        .active_fetch
                        .take()
                        .ok_or("fetch return without begin")?;
                    self.pending_fetch = Some((a.0, a.1));
                } else if let pi_history::Wire::Base(R::Fetch { fetch_context, .. }) = &mut record {
                    let p = self
                        .pending_fetch
                        .take()
                        .ok_or("fetch prologue without return")?;
                    require(*fetch_context == p.0, "raw fetch prologue context mismatch")?;
                    *fetch_context = p.1;
                }
            }
        }
        self.output = serde_json::to_vec(&record).map_err(|e| e.to_string())?;
        self.output.push(b'\n');
        self.position = 0;
        Ok(())
    }
    fn next(&mut self) -> Result<bool, String> {
        loop {
            if !fetch::line(&mut self.input, &mut self.raw)? {
                require(self.ended, "v2 history lacks complete footer")?;
                return Ok(false);
            }
            require(
                !self.ended && self.raw.ends_with(b"\n"),
                "truncated or trailing v2 record",
            )?;
            self.hash.update(&self.raw);
            let row: Wire = serde_json::from_slice(&self.raw).map_err(|e| e.to_string())?;
            match row {
                Wire::Schedule(s) => self.schedule(s)?,
                Wire::Legacy(r) => {
                    self.legacy(r)?;
                    return Ok(true);
                }
            }
        }
    }
}
impl<H: BufRead> Read for Projection<H> {
    fn read(&mut self, output: &mut [u8]) -> io::Result<usize> {
        let data = self.fill_buf()?;
        let count = data.len().min(output.len());
        output[..count].copy_from_slice(&data[..count]);
        self.consume(count);
        Ok(count)
    }
}
impl<H: BufRead> BufRead for Projection<H> {
    fn fill_buf(&mut self) -> io::Result<&[u8]> {
        if self.position == self.output.len() {
            self.output.clear();
            self.position = 0;
            self.next().map_err(io::Error::other)?;
        }
        Ok(&self.output[self.position..])
    }
    fn consume(&mut self, amount: usize) {
        self.position = (self.position + amount).min(self.output.len());
    }
}

pub fn inspect_pi_queue_boot_history<H: BufRead, F: BufRead + Seek>(
    history: H,
    fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
) -> Result<PiQueueHistoryReport, String> {
    let mut stream = Projection::new(history);
    let projection = pi_history::inspect_pi_boot_history(&mut stream, fetched, rom, firmware)?;
    require(
        stream.ended && stream.fill_buf().map_err(|e| e.to_string())?.is_empty(),
        "incomplete v2 source",
    )?;
    Ok(PiQueueHistoryReport {
        format: "plaid-pi-queue-history-report-v0".into(),
        scope: "finite_reference_pi_request_queue_dispatch_inspection".into(),
        history_sha256: format!("{:x}", stream.hash.finalize()),
        projection,
        records: stream.records,
        event_counts: stream.counts,
        accepted_requests: stream.requests.len() as u64,
        successful_insertions: stream.next_token,
        rejected_requests: stream
            .requests
            .iter()
            .filter(|r| r.outcome == Some(false))
            .count() as u64,
        requests_without_status: stream
            .requests
            .iter()
            .enumerate()
            .filter_map(|(n, r)| (!r.status).then_some(n as u64 + 1))
            .collect(),
        request_status_links: stream.statuses,
        unknown_statuses: stream.unknown,
        guest_completion_claimed: false,
        native_complete: false,
    })
}

pub fn verify_pi_queue_boot_history_report<H: BufRead, F: BufRead + Seek>(
    report: &PiQueueHistoryReport,
    history: H,
    fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
) -> Result<(), String> {
    require(
        *report == inspect_pi_queue_boot_history(history, fetched, rom, firmware)?,
        "PI queue report does not match complete sources/inputs",
    )
}
