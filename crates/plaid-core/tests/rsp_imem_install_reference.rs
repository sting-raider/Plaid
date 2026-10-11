use std::collections::BTreeMap;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Kind {
    Promote,
    DmaSink,
    CpuSink,
    Complete,
}

#[derive(Clone, Copy, Debug)]
struct Event {
    seq: u64,
    case_id: u32,
    kind: Kind,
    request: u64,
    pbus: u16,
    value: u64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Owner {
    Dma { request: u64, generation: u64 },
    Cpu { case_id: u32, generation: u64 },
}

#[derive(Debug)]
struct Replay {
    owners: Vec<Option<Owner>>,
    request_spans: BTreeMap<u64, Vec<Vec<u16>>>,
    completed: Vec<u64>,
}

fn byte_span(offset: u16, size: u16) -> Vec<u16> {
    (0..size)
        .map(|lane| offset.wrapping_add(lane) & 0x0fff)
        .collect()
}

fn replay(events: &[Event]) -> Result<Replay, &'static str> {
    let mut active = None;
    let mut last_promoted = 0;
    let mut generation = 0;
    let mut owners = vec![None; 4096];
    let mut request_spans = BTreeMap::<u64, Vec<Vec<u16>>>::new();
    let mut completed = Vec::new();

    for (index, event) in events.iter().enumerate() {
        if event.seq != index as u64 + 1 {
            return Err("non-contiguous event sequence");
        }
        match event.kind {
            Kind::Promote => {
                if active.is_some() || event.request <= last_promoted {
                    return Err("invalid request promotion");
                }
                active = Some(event.request);
                last_promoted = event.request;
                request_spans.insert(event.request, Vec::new());
            }
            Kind::DmaSink => {
                if active != Some(event.request) {
                    return Err("DMA sink not owned by active request");
                }
                generation += 1;
                let span = byte_span(event.pbus, 8);
                let owner = Owner::Dma {
                    request: event.request,
                    generation,
                };
                for byte in &span {
                    owners[usize::from(*byte)] = Some(owner);
                }
                request_spans
                    .get_mut(&event.request)
                    .ok_or("missing promoted request")?
                    .push(span);
            }
            Kind::CpuSink => {
                if event.request != 0 {
                    return Err("CPU sink forged as DMA-owned");
                }
                generation += 1;
                let owner = Owner::Cpu {
                    case_id: event.case_id,
                    generation,
                };
                for byte in byte_span(event.pbus, 4) {
                    owners[usize::from(byte)] = Some(owner);
                }
            }
            Kind::Complete => {
                if active != Some(event.request) {
                    return Err("completion does not match active request");
                }
                completed.push(event.request);
                active = None;
            }
        }
    }
    if active.is_some() {
        return Err("trace ended with active request");
    }
    Ok(Replay {
        owners,
        request_spans,
        completed,
    })
}

fn fixture() -> Vec<Event> {
    let raw = [
        (1, 1, Kind::Promote, 1, 0x200, 0),
        (2, 1, Kind::DmaSink, 1, 0x200, 0x1111_1111_1111_1111),
        (3, 1, Kind::CpuSink, 0, 0x204, 0x1111_1111),
        (4, 1, Kind::DmaSink, 1, 0x208, 0x2222_2222_2222_2222),
        (5, 1, Kind::Complete, 1, 0, 0),
        (6, 2, Kind::Promote, 2, 0x300, 0),
        (7, 2, Kind::DmaSink, 2, 0x300, 0x3333_3333_3333_3333),
        (8, 2, Kind::DmaSink, 2, 0x308, 0x4444_4444_4444_4444),
        (9, 2, Kind::Complete, 2, 0, 0),
        (10, 2, Kind::Promote, 3, 0x300, 0),
        (11, 2, Kind::DmaSink, 3, 0x300, 0x3333_3333_3333_3333),
        (12, 2, Kind::DmaSink, 3, 0x308, 0x4444_4444_4444_4444),
        (13, 2, Kind::Complete, 3, 0, 0),
        (14, 3, Kind::Promote, 4, 0xff8, 0),
        (15, 3, Kind::DmaSink, 4, 0xff8, 0x5555_5555_5555_5555),
        (16, 3, Kind::DmaSink, 4, 0x000, 0x6666_6666_6666_6666),
        (17, 3, Kind::Complete, 4, 0, 0),
        (18, 4, Kind::Promote, 5, 0x380, 0),
        (19, 4, Kind::DmaSink, 5, 0x380, 0x7777_7777_7777_7777),
        (20, 4, Kind::Complete, 5, 0, 0),
        (21, 4, Kind::Promote, 6, 0x388, 0),
        (22, 4, Kind::DmaSink, 6, 0x388, 0x8888_8888_8888_8888),
        (23, 4, Kind::Complete, 6, 0, 0),
    ];
    raw.into_iter()
        .map(|(seq, case_id, kind, request, pbus, value)| Event {
            seq,
            case_id,
            kind,
            request,
            pbus,
            value,
        })
        .collect()
}

#[test]
fn reproduces_request_scoped_effect_ownership_on_current_main() {
    let events = fixture();
    let result = replay(&events).expect("reference replay");

    assert_eq!(result.completed, vec![1, 2, 3, 4, 5, 6]);
    assert_eq!(
        result.request_spans[&1],
        vec![byte_span(0x200, 8), byte_span(0x208, 8)]
    );
    for byte in 0x204..0x208 {
        assert!(matches!(result.owners[byte], Some(Owner::Cpu { .. })));
    }
    for byte in (0x200..0x204).chain(0x208..0x210) {
        assert!(matches!(
            result.owners[byte],
            Some(Owner::Dma { request: 1, .. })
        ));
    }

    assert_eq!(events[6].value, events[10].value);
    assert_eq!(events[7].value, events[11].value);
    for byte in 0x300..0x310 {
        assert!(matches!(
            result.owners[byte],
            Some(Owner::Dma { request: 3, .. })
        ));
    }

    assert_eq!(
        result.request_spans[&4],
        vec![byte_span(0xff8, 8), byte_span(0x000, 8)]
    );
}

#[test]
fn rejects_wrong_owner_reused_id_missing_completion_and_bad_order() {
    let mut wrong_owner = fixture();
    wrong_owner[10].request = 2;
    assert!(replay(&wrong_owner).is_err());

    let mut reused = fixture();
    reused[9].request = 1;
    assert!(replay(&reused).is_err());

    let mut missing = fixture();
    missing.pop();
    assert!(replay(&missing).is_err());

    let mut reordered = fixture();
    reordered.swap(1, 2);
    assert!(replay(&reordered).is_err());
}
