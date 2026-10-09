use plaid_core::{
    EvidenceKind, GuestAddr,
    merge::merge_maps,
    program::{
        BasicBlock, CodeAddress, DelaySlot, DirectEdge, EdgeKind, Evidence, EvidenceRefs,
        ProgramMap, RomIdentity,
    },
};
use std::{hint::black_box, time::Instant};

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    }
}

fn refs() -> EvidenceRefs {
    ["bench".to_string()].into()
}

fn addr(index: usize) -> CodeAddress {
    CodeAddress {
        pc: GuestAddr(0x8000_0000 + u32::try_from(index).unwrap() * 8),
        image: "merge-bench".into(),
        generation: 0,
    }
}

fn synthetic_map(first: usize, count: usize, blocks: bool, edges: bool) -> ProgramMap {
    let mut map = ProgramMap::new(rom());
    map.evidence.insert(
        "bench".into(),
        Evidence {
            kind: EvidenceKind::Static,
            producer: "programmap-merge-scalability".into(),
            revision: "baseline".into(),
            detail: "synthetic valid scaling fact".into(),
        },
    );
    for index in first..first + count {
        if blocks {
            map.blocks.insert(BasicBlock {
                start: addr(index),
                size: 4,
                delay_slot_entry: false,
                evidence: refs(),
            });
        }
        if edges {
            map.direct_edges.insert(DirectEdge {
                site: addr(index),
                target: addr(index + 1),
                kind: EdgeKind::Fallthrough,
                delay_slot: DelaySlot::None,
                evidence: refs(),
            });
        }
    }
    map.validate().unwrap();
    map
}

fn timed_merge(total: usize, blocks: bool, edges: bool) -> f64 {
    let half = total / 2;
    let left = synthetic_map(0, half, blocks, edges);
    let right = synthetic_map(half, total - half, blocks, edges);
    let started = Instant::now();
    let merged = black_box(merge_maps(black_box(&left), black_box(&right)).unwrap());
    let elapsed = started.elapsed().as_secs_f64() * 1000.0;
    if blocks {
        assert_eq!(merged.blocks.len(), total);
    }
    if edges {
        assert_eq!(merged.direct_edges.len(), total);
    }
    elapsed
}

fn median(mut values: Vec<f64>) -> f64 {
    values.sort_by(f64::total_cmp);
    values[values.len() / 2]
}

#[test]
#[ignore = "release-build scaling benchmark; run explicitly"]
fn benchmark_programmap_merge_scaling() {
    let sizes: Vec<usize> = std::env::var("MERGE_BENCH_SIZES")
        .unwrap_or_else(|_| "500,1000,2000,4000,8000".into())
        .split(',')
        .map(|value| value.parse().unwrap())
        .collect();
    let repeats: usize = std::env::var("MERGE_BENCH_REPEATS")
        .unwrap_or_else(|_| "3".into())
        .parse()
        .unwrap();

    for (axis, blocks, edges) in [("blocks", true, false), ("edges", false, true)] {
        // Warm allocator/code paths without contaminating the measured series.
        black_box(timed_merge(128, blocks, edges));
        let mut previous = None;
        for &size in &sizes {
            let samples = (0..repeats)
                .map(|_| timed_merge(size, blocks, edges))
                .collect::<Vec<_>>();
            let med = median(samples.clone());
            let ratio = previous.map(|old| med / old).unwrap_or(0.0);
            println!(
                "MERGE_SCALE axis={axis} facts={size} median_ms={med:.3} ratio_from_previous={ratio:.3} samples_ms={samples:?}"
            );
            previous = Some(med);
        }
    }
}
