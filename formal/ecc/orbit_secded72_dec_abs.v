// Formal-only abstraction of the SECDED decoder (orbit_secded72_dec) for the
// bank proofs in formal/ecc/orbit_ecc_bank.sby.
//
// Read with `read_verilog -overwrite` after rtl/ecc/orbit_secded72.v, it
// replaces the decoder inside orbit_ecc_bank by free outputs. The bank
// harness (orbit_ecc_bank_fv.sv) then constrains those outputs, through the
// bank's way_cw/way_ce/way_ue nets, to the decoder contract proven for the
// real decoder by formal/ecc/orbit_secded72.sby (S0, S1, S2): for a stored
// word equal to a codeword G = {enc(d), d} XOR an error pattern E,
//   |E| = 0  -> corrected word = G, ce = 0, ue = 0
//   |E| = 1  -> corrected word = G, ce = 1, ue = 0
//   |E| = 2  -> corrected word = received word, ce = 0, ue = 1
// This keeps the parity arithmetic (hard for SAT solvers) out of the
// sequential proofs; the composition argument is in rtl/ecc/README.md.

`default_nettype none

module orbit_secded72_dec (
    input  wire [63:0] data_in,
    input  wire [7:0]  check_in,
    output wire [63:0] data_out,
    output wire [7:0]  check_out,
    output wire        ce,
    output wire        ue,
    output wire [7:0]  syndrome
);
    (* anyseq *) reg [63:0] f_data;
    (* anyseq *) reg [7:0]  f_check;
    (* anyseq *) reg        f_ce;
    (* anyseq *) reg        f_ue;
    (* anyseq *) reg [7:0]  f_syndrome;

    assign data_out  = f_data;
    assign check_out = f_check;
    assign ce        = f_ce;
    assign ue        = f_ue;
    assign syndrome  = f_syndrome;

    // The inputs are intentionally unused: the harness states the contract.
    wire unused_ok = &{1'b0, data_in, check_in};
endmodule

`default_nettype wire
