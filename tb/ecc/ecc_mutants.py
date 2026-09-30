#!/usr/bin/env python3
"""Write deliberately broken copies of the ECC RTL (negative controls).

Usage: ecc_mutants.py <rtl/ecc dir> <out dir> [mutant ...]

Each mutant is a directory <out dir>/<name>/ holding orbit_secded72.v and
orbit_ecc_bank.v, one of them changed by an exact text substitution. The
script fails if a substitution does not match exactly the expected number of
times, so an RTL edit cannot silently turn a mutant into the original design.
Without mutant names, all are written; the names are printed one per line.
"""

import os
import sys

CODEC = "orbit_secded72.v"
BANK = "orbit_ecc_bank.v"

# name: (file, old text, new text, expected count, what the checks must catch)
MUTANTS = {
    # Data bit 0 loses row 0 of its H column: weight 2 (even), so a single
    # error in bit 0 looks like a double error and some double errors alias.
    "codec_even_col": (CODEC,
                       "localparam [63:0] H_ROW0 = 64'hf1000000001fffff;",
                       "localparam [63:0] H_ROW0 = 64'hf1000000001ffffe;", 1,
                       "Hsiao column weights / single-error correction"),
    # The scrubber finds errors but never writes the corrected word back.
    "bank_no_writeback": (BANK,
                          "wire [INTERLEAVE-1:0] scrub_fix = way_ce & {INTERLEAVE{scrub_go}};",
                          "wire [INTERLEAVE-1:0] scrub_fix = {INTERLEAVE{1'b0}};", 1,
                          "scrub repair / array contents"),
    # Codewords stored side by side instead of bit-interleaved (consistent on
    # the read and write side, so fault-free behaviour is unchanged; the fourth
    # match is the layout comment).
    "bank_no_interleave": (BANK,
                           "k*INTERLEAVE + w", "w*CW + k", 4,
                           "adjacent 2-bit upset becomes a double error"),
    # Error counters wrap instead of saturating.
    "bank_cnt_wrap": (BANK,
                      "ce_count <= (ce_sum > CNT_MAX) ? {CNT_W{1'b1}} : ce_sum[CNT_W-1:0];",
                      "ce_count <= ce_sum[CNT_W-1:0];", 1,
                      "saturating CE counter"),
    # The last-error record does not give UE events precedence.
    "bank_log_prio": (BANK,
                      "if (ev_is_ue ? ev_ue[i] : ev_ce[i])",
                      "if (ev_ce[i] | ev_ue[i])", 1,
                      "last_err_* UE precedence"),
    # The read-side de-interleaving swaps the two ways (the write side is
    # right): reads and scrub decode the neighbouring codeword. The unbounded
    # bank proofs abstract the decoder, so they need assertion A5 (decoder
    # input = stored codeword) to see this.
    "bank_read_way_swap": (BANK,
                           "assign cw_raw[k] = dec_bits[k*INTERLEAVE + w];",
                           "assign cw_raw[k] = dec_bits[k*INTERLEAVE + (INTERLEAVE - 1 - w)];", 1,
                           "read-side bit mapping / decoder input"),
    # The scrubber also runs while the read port is busy (steals the decoders).
    "bank_scrub_on_read": (BANK,
                           "wire                  scrub_go  = scrub_en & ~wr_en & ~rd_en;",
                           "wire                  scrub_go  = scrub_en & ~wr_en;", 1,
                           "scrub only when idle / scrub_row"),
}


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    src, out = argv[1], argv[2]
    names = argv[3:] or list(MUTANTS)
    for name in names:
        fname, old, new, count, _ = MUTANTS[name]
        mdir = os.path.join(out, name)
        os.makedirs(mdir, exist_ok=True)
        for f in (CODEC, BANK):
            text = open(os.path.join(src, f)).read()
            if f == fname:
                found = text.count(old)
                if found != count:
                    print("ecc_mutants: %s: expected %d match(es) in %s, found %d"
                          % (name, count, f, found))
                    return 1
                text = text.replace(old, new)
            with open(os.path.join(mdir, f), "w") as fh:
                fh.write(text)
        print(name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
