// ORBIT-AI demonstrator: one copy of a redundantly stored register.
//
// Every redundant copy (duplicated accumulators and result registers, the
// three thermal-state copies) is its own instance of this module. The
// keep_hierarchy attribute stops synthesis from flattening the copies together
// and then merging flip-flops whose D inputs are identical, which is exactly
// what happens to TMR copies that are all written from one voter. Signal
// attributes on the reg alone are not enough for that, so synthesis scripts
// must preserve this hierarchy (or re-apply keep to these flip-flops) and the
// storage audit in scripts/ checks the result.

`default_nettype none

(* keep_hierarchy *)
module orbit_keep_reg #(
    parameter integer   W         = 32,
    parameter [W-1:0]   RESET_VAL = {W{1'b0}}
) (
    input  wire         clk,
    input  wire         rst_n,  // synchronous, active low
    input  wire         en,
    input  wire [W-1:0] d,
    output reg  [W-1:0] q
);

    always @(posedge clk) begin
        if (!rst_n)
            q <= RESET_VAL;
        else if (en)
            q <= d;
    end

endmodule

`default_nettype wire
