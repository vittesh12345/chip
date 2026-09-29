# ECC extension: (72,64) SECDED codec and scrubbed, interleaved bank

This directory is an extension toward the target architecture's "Protected
SRAM / SECDED ECC + interleaving / ECC scrub" item of the ORBIT-AI concept
brief. It is **not** part of the built demonstrator: `orbit_demo` does not
instantiate anything here, and `$(RTL)` in the top-level Makefile does not
list these files. The make rules are in `mk/ecc.mk` (`make ecc`), the
evidence in `reports/ecc/`.

Nothing here is radiation-qualified. The bank is a flip-flop array standing
in for an SRAM macro; its size (16 rows) is a demonstrator size, not the
target's 32 MiB.

| File | Contents |
|---|---|
| `orbit_secded72.v` | `orbit_secded72_enc`, `orbit_secded72_dec`: Hsiao (72,64) SECDED encoder and decoder, purely combinational |
| `orbit_ecc_bank.v` | `orbit_ecc_bank`: DEPTH x INTERLEAVE words of 64 bits, bit-interleaved codewords, read/write port, background scrubber, error log |
| `gen_hsiao72.py` | Generator of the H matrix block in `orbit_secded72.v`; `--check` verifies the file against the construction |

Verilog-2005, single clock `clk`, synchronous active-low reset `rst_n`.

## 1. Code

Codeword layout: `cw[63:0]` = data, `cw[71:64]` = check bits.

The parity-check matrix H is a Hsiao odd-weight-column matrix:

* check bit j (codeword bit 64+j): unit column (weight 1);
* data bits 0..55: the 56 weight-3 columns, in lexicographic order of the row
  triple;
* data bits 56..63: `0b00011111` rotated left by 0..7 (weight 5).

Every row of the data part has 26 ones, so the eight parity trees are the
same size. All 72 columns are distinct, non-zero and of odd weight, hence:

| Errors | Syndrome | Decoder result |
|---|---|---|
| 0 | 0 | data unchanged, `ce = 0`, `ue = 0` |
| 1 | the column of the flipped bit (odd weight) | bit corrected, `ce = 1`, `ue = 0` |
| 2 | XOR of two distinct odd columns: non-zero, even weight, equal to no column | nothing flipped, `ce = 0`, `ue = 1` |
| 3 or more | not guaranteed | may be miscorrected (`ce = 1`, wrong data) or flagged `ue` |

Three-bit errors are never silent (the syndrome has odd weight, so it is
non-zero), but in the simulation about 56 % of random triples are
miscorrected; SECDED does not cover them.

### `orbit_secded72_enc`

| Port | Dir | Width | Meaning |
|---|---|---|---|
| `data` | in | 64 | Data word |
| `check` | out | 8 | Check bits: `check[r]` = XOR of the data bits in row r of H (even parity per row) |

### `orbit_secded72_dec`

| Port | Dir | Width | Meaning |
|---|---|---|---|
| `data_in` | in | 64 | Received data bits (`cw[63:0]`) |
| `check_in` | in | 8 | Received check bits (`cw[71:64]`) |
| `data_out` | out | 64 | Corrected data; the received data when `ue` |
| `check_out` | out | 8 | Corrected check bits; the received check bits when `ue` |
| `ce` | out | 1 | Exactly one bit was in error and has been corrected |
| `ue` | out | 1 | Uncorrectable: non-zero syndrome that matches no column |
| `syndrome` | out | 8 | H x received word; 0 means no error detected |

`ce` and `ue` are never both 1. The decoder computes its syndrome with an
encoder instance and derives each error-locator column by encoding a unit
vector (a constant that synthesis folds away), so the encoder and decoder
cannot disagree about H.

## 2. `orbit_ecc_bank`

### Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `DEPTH` | 16 | Physical rows; power of 2, at least 2 |
| `INTERLEAVE` | 2 | Codewords per row; power of 2, at least 1 |
| `CNT_W` | 16 | Width of the saturating error counters, at least 1 |

Illegal values stop elaboration (they instantiate a module that does not
exist). `AW = log2(DEPTH*INTERLEAVE)` is the word-address width (5 at the
defaults).

### Organisation

Each physical row holds `INTERLEAVE` (72,64) codewords, bit-interleaved:
codeword bit `k` of way `w` is stored at physical column
`k*INTERLEAVE + w`. Physically adjacent cells therefore belong to different
codewords, and an upset of up to `INTERLEAVE` adjacent cells of one row is
at most one bit error per codeword, which SECDED corrects. Without
interleaving (`INTERLEAVE = 1`) an adjacent 2-bit upset is a double error in
one codeword: detected, not corrected (the formal task `il1_neg` shows this).

Word address `addr = {row, way}`: `row = addr[AW-1:log2(INTERLEAVE)]`,
`way = addr[log2(INTERLEAVE)-1:0]`.

### Ports

| Port | Dir | Width | Meaning |
|---|---|---|---|
| `clk`, `rst_n` | in | 1 | Clock; synchronous reset, active low |
| `wr_en` | in | 1 | Write `wr_data` to `wr_addr` at this rising edge |
| `wr_addr` | in | AW | Write address |
| `wr_data` | in | 64 | Write data (encoded inside the bank) |
| `rd_en` | in | 1 | Read `rd_addr` at this rising edge |
| `rd_addr` | in | AW | Read address |
| `rd_valid` | out | 1 | `rd_en` of the previous cycle (a one-cycle pulse per read) |
| `rd_data` | out | 64 | Corrected data of the last read (uncorrected data if `rd_ue`) |
| `rd_ce` | out | 1 | The last read corrected a single-bit error |
| `rd_ue` | out | 1 | The last read found an uncorrectable (double) error |
| `scrub_en` | in | 1 | Allow the scrubber to use idle cycles |
| `log_clear` | in | 1 | Clear `ce_count`, `ue_count` and `last_err_*` (events of the same cycle are kept) |
| `scrub_row` | out | log2(DEPTH) | Row the scrubber will visit next |
| `ce_count` | out | CNT_W | Correctable-error events, saturating at all ones |
| `ue_count` | out | CNT_W | Uncorrectable-error events, saturating at all ones |
| `last_err_valid` | out | 1 | An error event has been recorded since reset / `log_clear` |
| `last_err_ue` | out | 1 | The recorded event was uncorrectable |
| `last_err_addr` | out | AW | Word address of the recorded event |

### Protocol

* **Write.** With `wr_en` high at a rising edge, `{enc(wr_data), wr_data}`
  replaces the addressed codeword; the other codewords of the row are not
  changed. There is no busy signal: every write is accepted.
* **Read, latency 1.** With `rd_en` high at a rising edge, the addressed
  codeword is decoded; after the edge `rd_valid` is 1 for one cycle and
  `rd_data`, `rd_ce`, `rd_ue` hold the result. `rd_data`/`rd_ce`/`rd_ue`
  keep their value until the next read. A read never writes the corrected
  word back; repair is the scrubber's job (or the next write).
* **Read and write in the same cycle** are both performed. A read of the
  address being written returns the old contents (read-first).
* **Scrubber.** In every cycle with `scrub_en & ~wr_en & ~rd_en` ("idle")
  it decodes all codewords of row `scrub_row`, writes back the corrected
  codeword of every way that had a single-bit error, leaves ways with an
  uncorrectable error unchanged, and advances `scrub_row` by one (wrapping).
  A single-bit error is therefore repaired within `DEPTH` idle cycles after
  it appears, whatever the traffic in between (proven, section 3). Under
  continuous read/write traffic the scrubber makes no progress; there is no
  forced scrub slot.
* **Error log.** Every error the decoders see is an event: the addressed
  codeword of a read, and every codeword of a row the scrubber visits.
  `ce_count`/`ue_count` add the number of CE/UE events per cycle and saturate.
  `last_err_*` records the most recent event; if one cycle has several
  (scrub of a row with errors in several ways), UE events take precedence,
  then the lowest way. The counters count events, not distinct errors: a
  double error that stays in the array is counted again at every scrub pass
  and every read. `log_clear` zeroes the log first, then the events of the
  same cycle are added.
* **Reset** writes all-zero rows, which are valid codewords (data 0), so
  every word reads 0 after reset. A real SRAM macro would need an
  initialisation sweep instead.

### Verification hook

With the macro `ORBIT_ECC_UPSET` defined (formal runs only; never for
synthesis) the bank declares an undriven wire `upset` that is XORed into the
array at every clock edge; the formal harness drives it to model upsets.
Without the macro `upset` is the constant 0. Simulation injects upsets by
hierarchical writes to `cells` instead.

## 3. Verification (`make ecc`)

Results and run times: `reports/ecc/summary.md`.

* `ecc-hsiao`: `gen_hsiao72.py --check` confirms the H block of the codec
  equals the construction and has the Hsiao properties.
* `ecc-sim`: `tb/ecc/tb_orbit_secded72.v` checks every single and every
  double error position on random words against a reference encoder built
  from the construction rule; `tb/ecc/tb_orbit_ecc_bank.v` runs random
  traffic with random single, adjacent 2-bit and double upsets against an
  independent reference model (data, error patterns, scrub pointer, log) and
  compares the whole array bit for bit.
* `ecc-sim-mutants`: the benches must fail on six broken RTL copies.
* `ecc-formal`:
  * `orbit_secded72.sby` proves, for every 64-bit data word and every error
    position(s): no error returns data and check bits with no flags; any
    single-bit error is corrected with `ce = 1, ue = 0`; any double-bit error
    gives `ue = 1, ce = 0` and flips nothing (so is never miscorrected). The
    codec is combinational, so the one-step proof is complete.
  * `orbit_ecc_bank.sby` proves the bank by k-induction (unbounded) for
    `DEPTH = 16, INTERLEAVE = 2` against a reference model of the array: the
    array always equals the model, reads return the last written data with
    exact CE/UE flags, the log equals the model, and a single error is
    repaired within `DEPTH` idle cycles. Upsets (1 bit or 2 adjacent bits of
    a row, any number over time) are free in `sec` as long as none lands on
    a codeword that already holds an error, and may create double errors in
    `ded`. **Decomposition:** in these proofs the bank's decoder is replaced
    by free outputs constrained to the contract that `orbit_secded72.sby`
    proves for the real decoder (for a stored word G xor E with G a
    codeword produced by the encoder: |E| = 0 or 1 gives G with the right
    flag, |E| = 2 gives UE and the unchanged word). The bank proof shows
    G's data is the last written data, and G always comes from the bank's
    own encoder, so the two proofs compose into the end-to-end statement.
    The direct end-to-end check with the real decoder (`e2e_clean`,
    `e2e_upset`) is only a bounded BMC (5 and 4 steps from reset at
    `DEPTH = 2`; too short for the scrub bound),
    because the parity arithmetic of chained 64-bit codecs defeated
    k-induction in the solvers tried and makes BMC grow fast with depth.
  * Negative controls that must fail: `il1_neg` (the `sec` proof with
    `INTERLEAVE = 1`), the codec proof on a copy with an even-weight column,
    and the `sec` proof on a bank that never writes back.
* `ecc-synth`: Yosys generic synthesis of the encoder, decoder and bank.
