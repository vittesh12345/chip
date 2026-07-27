// ORBIT-AI 4-lane INT8 digital demonstrator (top level).
//
// A small, testable slice of the ORBIT-AI concept: LANES independent signed
// INT8 multiply / INT32 accumulate lanes behind a valid/ready input stream, a
// one-result output buffer, duplicated accumulator and result storage with a
// sticky mismatch fault-stop, and a triplicated thermal state machine that
// throttles, stops and recovers input admission.
//
// Not included: automatic replay, ECC SRAM, floating point, physical sensor
// interfaces, or any radiation hardness claim. See docs/SPEC.md.
//
// Input beat (accepted when in_valid && in_ready):
//   lane i: acc_i = (in_first ? 0 : acc_i) + in_a[i] * in_b[i]   (signed, wraps mod 2^32)
//   in_last: the updated acc_i of every lane is copied to the output buffer.
// Output: out_data holds one result (lane i at bits [32*i +: 32]) and is
// presented while out_valid is high until out_ready is seen.

`default_nettype none

module orbit_demo #(
    parameter integer      LANES      = 4,
    parameter signed [7:0] T_THROTTLE = 8'sd80,
    parameter signed [7:0] T_STOP     = 8'sd95,
    parameter signed [7:0] T_RECOVER  = 8'sd70
) (
    input  wire                clk,
    input  wire                rst_n,         // synchronous, active low

    // Input stream: one INT8 pair per lane per beat.
    input  wire                in_valid,
    output wire                in_ready,
    input  wire                in_first,
    input  wire                in_last,
    input  wire [LANES*8-1:0]  in_a,
    input  wire [LANES*8-1:0]  in_b,

    // Output stream: one-result buffer.
    output wire                out_valid,
    input  wire                out_ready,
    output wire [LANES*32-1:0] out_data,

    // Thermal sensor (signed whole degrees Celsius).
    input  wire                temp_valid,
    input  wire [7:0]          temp_c,

    // Control and status.
    input  wire                clear_fault,   // clear the fault and zero both copies of all lane storage
    output wire                fault,         // sticky: redundant copies disagreed
    output wire [1:0]          therm_state,   // 0 NORMAL, 1 THROTTLE, 2 STOP (3 unused, treated as STOP)
    output wire                therm_repair,  // thermal copies disagree this cycle
    output wire                shutdown_req   // thermal STOP: request safe shutdown
);

    wire [LANES-1:0] lane_mismatch;
    wire             mismatch = |lane_mismatch;

    reg fault_q;
    reg out_valid_q;

    wire admit;

    // A result is only presented while both copies of every lane agree and no
    // fault has been latched, so a detected upset never leaves the chip.
    assign out_valid = out_valid_q & ~fault_q & ~mismatch;

    wire out_fire = out_valid & out_ready;

    // The output buffer holds one result. Input is blocked while it is full
    // and not being drained this cycle (this also covers non-final beats).
    assign in_ready = admit & ~fault_q & ~mismatch & ~clear_fault &
                      (~out_valid_q | out_ready);

    wire in_fire = in_valid & in_ready;

    genvar i;
    generate
        for (i = 0; i < LANES; i = i + 1) begin : g_lane
            orbit_mac_lane u_lane (
                .clk      (clk),
                .rst_n    (rst_n),
                .clr      (clear_fault),
                .mac_en   (in_fire),
                .first    (in_first),
                .last     (in_last),
                .a        (in_a[8*i +: 8]),
                .b        (in_b[8*i +: 8]),
                .result   (out_data[32*i +: 32]),
                .mismatch (lane_mismatch[i])
            );
        end
    endgenerate

    orbit_thermal_tmr #(
        .T_THROTTLE (T_THROTTLE),
        .T_STOP     (T_STOP),
        .T_RECOVER  (T_RECOVER)
    ) u_thermal (
        .clk        (clk),
        .rst_n      (rst_n),
        .temp_valid (temp_valid),
        .temp_c     (temp_c),
        .state      (therm_state),
        .admit      (admit),
        .repair     (therm_repair)
    );

    always @(posedge clk) begin
        if (!rst_n) begin
            fault_q     <= 1'b0;
            out_valid_q <= 1'b0;
        end else if (clear_fault) begin
            fault_q     <= 1'b0;
            out_valid_q <= 1'b0;
        end else begin
            if (mismatch)
                fault_q <= 1'b1;
            if (in_fire && in_last)
                out_valid_q <= 1'b1;
            else if (out_fire)
                out_valid_q <= 1'b0;
        end
    end

    assign fault        = fault_q;
    assign shutdown_req = therm_state[1];

endmodule

`default_nettype wire
