#!/usr/bin/env python3
"""Bounded exact-pin experiment for n64sym signature identity semantics."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

PIN = "ccf4600f3389f1a84bde23339225cf372fdf7712"
N64SYM_URL = "https://github.com/shygoo/n64sym.git"


def sh(cmd: list[str], *, cwd: Path | None = None, capture: bool = True) -> str:
    p = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    return p.stdout if capture else ""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_sig(path: Path) -> list[dict]:
    symbols: list[dict] = []
    current: dict | None = None
    for line_no, raw in enumerate(path.read_text(errors="strict").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        toks = line.split()
        if toks[0].startswith("."):
            if current is None or len(toks) < 3:
                raise AssertionError(f"bad relocation line {line_no}: {raw}")
            current["relocs"].append(
                {"type": toks[0], "name": toks[1], "offsets": [int(x, 0) for x in toks[2:]]}
            )
            continue
        if len(toks) != 4:
            raise AssertionError(f"bad symbol line {line_no}: {raw}")
        current = {
            "name": toks[0],
            "size": int(toks[1], 0),
            "crc_a": int(toks[2], 0),
            "crc_b": int(toks[3], 0),
            "relocs": [],
        }
        symbols.append(current)
    return symbols


def symbol_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


def build_identical_object(as_bin: str, out: Path, name: str) -> None:
    asm = out.with_suffix(".s")
    asm.write_text(
        ".set noreorder\n"
        ".text\n"
        ".align 2\n"
        f".globl {name}\n"
        f".type {name}, @function\n"
        f"{name}:\n"
        "  addiu $2, $0, 1\n"
        "  jr $31\n"
        "  nop\n"
        f".size {name}, .-{name}\n"
    )
    sh([as_bin, "-EB", "-mips3", "-o", str(out), str(asm)])


def build_reloc_object(as_bin: str, out: Path) -> None:
    asm = out.with_suffix(".s")
    asm.write_text(
        ".set noreorder\n"
        ".text\n"
        ".align 2\n"
        ".globl gamma\n"
        ".type gamma, @function\n"
        "gamma:\n"
        "  jal external_target\n"
        "  nop\n"
        "  jr $31\n"
        "  nop\n"
        ".size gamma, .-gamma\n"
    )
    sh([as_bin, "-EB", "-mips3", "-o", str(out), str(asm)])


def make_harness(repo: Path, out: Path) -> Path:
    cpp = out / "signature_harness.cpp"
    cpp.write_text(
        '#include <fstream>\n'
        '#include <iostream>\n'
        '#include <vector>\n'
        '#include "signaturefile.h"\n'
        'static std::vector<unsigned char> load(const char* p) {\n'
        '  std::ifstream f(p, std::ios::binary);\n'
        '  return std::vector<unsigned char>((std::istreambuf_iterator<char>(f)), {});\n'
        '}\n'
        'int main(int argc, char** argv) {\n'
        '  if (argc != 3) return 2;\n'
        '  CSignatureFile sig; if (!sig.Load(argv[1]) || sig.GetNumSymbols() != 1) return 3;\n'
        '  auto b = load(argv[2]); if (b.size() < sig.GetSymbolSize(0)) return 4;\n'
        '  std::cout << (sig.TestSymbol(0, b.data()) ? "MATCH" : "NO_MATCH") << "\\n";\n'
        '}\n'
    )
    exe = out / "signature_harness"
    sh([
        "g++", "-std=c++11", "-O2",
        "-I", str(repo / "src"), "-I", str(repo / "include"),
        str(cpp), str(repo / "src/signaturefile.cpp"), str(repo / "src/crc32.c"),
        "-o", str(exe),
    ])
    return exe


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n64sym", type=Path, help="existing exact-pin checkout; otherwise clone")
    ap.add_argument("--report", type=Path, default=Path(__file__).with_name("report.json"))
    args = ap.parse_args()

    with tempfile.TemporaryDirectory(prefix="plaid-n64sym-") as td_s:
        td = Path(td_s)
        if args.n64sym:
            repo = args.n64sym.resolve()
        else:
            repo = td / "n64sym"
            sh(["git", "clone", "--quiet", N64SYM_URL, str(repo)])
        sh(["git", "checkout", "--quiet", PIN], cwd=repo)
        head = sh(["git", "rev-parse", "HEAD"], cwd=repo).strip()
        assert head == PIN, (head, PIN)

        license_text = (repo / "LICENSE.md").read_text()
        assert "Permission is hereby granted, free of charge" in license_text

        generator = (repo / "src/n64sig.cpp").read_text()
        matcher = (repo / "src/signaturefile.cpp").read_text()
        assert "m_SymbolMap.count(symbolEntry.crc_b)" in generator
        assert "m_SymbolMap[symbolEntry.crc_b] = symbolEntry" in generator
        assert "ReadStrippedWord" in matcher
        assert "dst[0] &= 0xFC" in matcher and "dst[2] = 0x00" in matcher

        builtin_path = repo / "src/builtin_signatures.sig"
        builtin = parse_sig(builtin_path)
        full_keys: dict[tuple[int, int, int], list[str]] = {}
        crc_b_keys: dict[int, list[str]] = {}
        for s in builtin:
            full_keys.setdefault((s["size"], s["crc_a"], s["crc_b"]), []).append(s["name"])
            crc_b_keys.setdefault(s["crc_b"], []).append(s["name"])
        full_ambiguous = {str(k): v for k, v in full_keys.items() if len(v) > 1}
        crcb_ambiguous = {f"0x{k:08x}": v for k, v in crc_b_keys.items() if len(v) > 1}

        # Build the actual pinned generator. Avoid its static-link default; this is
        # a research executable, not a redistribution artifact.
        sh(["make", "n64sig", "LDFLAGS=-s -Wl,--gc-sections -lm -lpthread"], cwd=repo)
        n64sig = repo / "bin/n64sig"
        assert n64sig.exists()

        as_bin = shutil.which("mips-linux-gnu-as")
        objcopy = shutil.which("mips-linux-gnu-objcopy")
        if not as_bin or not objcopy:
            raise RuntimeError("binutils-mips-linux-gnu is required")

        fixture = td / "fixture"
        fixture.mkdir()
        alpha = fixture / "alpha.o"
        beta = fixture / "beta.o"
        build_identical_object(as_bin, alpha, "alpha")
        build_identical_object(as_bin, beta, "beta")

        ab = sh([str(n64sig), "-v", "-l", str(alpha), "-l", str(beta)])
        ba = sh([str(n64sig), "-v", "-l", str(beta), "-l", str(alpha)])
        ab_symbols = symbol_lines(ab)
        ba_symbols = symbol_lines(ba)
        assert len(ab_symbols) == 1 and ab_symbols[0].startswith("alpha "), ab
        assert len(ba_symbols) == 1 and ba_symbols[0].startswith("beta "), ba
        assert "skipped beta (have alpha" in ab
        assert "skipped alpha (have beta" in ba

        # Prove relocation normalization with the exact pinned scanner's
        # CSignatureFile::TestSymbol implementation, not a reimplemented matcher.
        gamma_obj = fixture / "gamma.o"
        build_reloc_object(as_bin, gamma_obj)
        gamma_sig = fixture / "gamma.sig"
        gamma_sig.write_text(sh([str(n64sig), "-l", str(gamma_obj)]))
        gamma_syms = parse_sig(gamma_sig)
        assert len(gamma_syms) == 1 and gamma_syms[0]["name"] == "gamma"
        assert any(r["type"] == ".targ26" and 0 in r["offsets"] for r in gamma_syms[0]["relocs"]), gamma_sig.read_text()

        gamma_bin = fixture / "gamma.bin"
        sh([objcopy, "-O", "binary", "-j", ".text", str(gamma_obj), str(gamma_bin)])
        original = bytearray(gamma_bin.read_bytes())
        assert len(original) >= 16
        word = struct.unpack(">I", original[:4])[0]
        assert (word >> 26) == 0x03, hex(word)  # JAL

        relocated = bytearray(original)
        relocated[:4] = struct.pack(">I", (word & 0xFC000000) | 0x00123456)
        relocated_path = fixture / "gamma_relocated.bin"
        relocated_path.write_bytes(relocated)

        nonreloc = bytearray(original)
        nonreloc[4] ^= 0x01  # delay-slot byte, not covered by relocation stripping
        nonreloc_path = fixture / "gamma_nonreloc_mutation.bin"
        nonreloc_path.write_bytes(nonreloc)

        harness = make_harness(repo, fixture)
        original_match = sh([str(harness), str(gamma_sig), str(gamma_bin)]).strip()
        relocated_match = sh([str(harness), str(gamma_sig), str(relocated_path)]).strip()
        nonreloc_match = sh([str(harness), str(gamma_sig), str(nonreloc_path)]).strip()
        assert original_match == "MATCH"
        assert relocated_match == "MATCH"
        assert nonreloc_match == "NO_MATCH"
        assert bytes(original) != bytes(relocated)

        report = {
            "plaid_experiment": "n64sym-signature-evidence-v1",
            "n64sym_revision": head,
            "source_sha256": {
                "LICENSE.md": sha256(repo / "LICENSE.md"),
                "src/n64sig.cpp": sha256(repo / "src/n64sig.cpp"),
                "src/signaturefile.cpp": sha256(repo / "src/signaturefile.cpp"),
                "src/builtin_signatures.sig": sha256(builtin_path),
            },
            "builtin_corpus": {
                "symbols": len(builtin),
                "unique_crc_b": len(crc_b_keys),
                "unique_full_tuple": len(full_keys),
                "symbols_with_relocations": sum(bool(s["relocs"]) for s in builtin),
                "duplicate_crc_b_groups": len(crcb_ambiguous),
                "duplicate_full_tuple_groups": len(full_ambiguous),
            },
            "generator_identity_adversary": {
                "alpha_then_beta_signature": ab_symbols[0],
                "beta_then_alpha_signature": ba_symbols[0],
                "alpha_then_beta_warning": next(ln for ln in ab.splitlines() if "skipped beta" in ln),
                "beta_then_alpha_warning": next(ln for ln in ba.splitlines() if "skipped alpha" in ln),
                "conclusion": "byte-identical distinct symbol names collapse to the first crc_b identity",
            },
            "relocation_normalization": {
                "signature": gamma_sig.read_text().strip().splitlines(),
                "original_word": f"0x{word:08x}",
                "relocated_word": f"0x{struct.unpack('>I', relocated[:4])[0]:08x}",
                "original_match": original_match,
                "relocated_match": relocated_match,
                "nonreloc_mutation_match": nonreloc_match,
                "original_sha256": hashlib.sha256(original).hexdigest(),
                "relocated_sha256": hashlib.sha256(relocated).hexdigest(),
                "nonreloc_sha256": hashlib.sha256(nonreloc).hexdigest(),
                "conclusion": "byte-distinct relocation targets intentionally inhabit one n64sym signature class",
            },
            "result": "VALIDATED",
            "does_not_prove": [
                "that any n64sym match is wrong",
                "that the built-in corpus contains crc collisions after generator deduplication",
                "that a symbol hint establishes code reachability, byte provenance, immutability, or closure",
            ],
        }
        encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded)
        print(encoded, end="")
        print("report_sha256=" + hashlib.sha256(encoded.encode()).hexdigest())


if __name__ == "__main__":
    main()
