// ORBIT-AI demonstrator: triplicated thermal state with feedback repair.
//
// Three copies of the 2-bit thermal state are majority-voted. The next state
// is computed once from the voted state and written back into all three
// copies, so a single upset copy is repaired at the next clock edge.
//
// Thresholds are illustrative prototype values, not device ratings:
//   NORMAL   -> THROTTLE  when temp >= T_THROTTLE (80 C)
//   any      -> STOP      when temp >= T_STOP (95 C) or the sensor is invalid
//   THROTTLE -> NORMAL    when temp <= T_RECOVER (70 C)
//   STOP     -> NORMAL    when temp <= T_RECOVER (70 C) and the sensor is valid
// Reset puts every copy in STOP, so nothing is admitted until the first valid
// reading at or below T_RECOVER.
//
// In THROTTLE, input is admitted on alternate cycles only. The phase bit that
// chooses those cycles, the voter, and the sensor inputs are single points of
// failure.

`default_nettype none

module orbit_thermal_tmr #(
    parameter signed [7:0] T_THROTTLE = 8'sd80,
    parameter signed [7:0] T_STOP     = 8'sd95,
    parameter signed [7:0] T_RECOVER  = 8'sd70
) (
    input  wire       clk,
    input  wire       rst_n,       // synchronous, active low
    input  wire       temp_valid,
    input  wire [7:0] temp_c,      // signed whole degrees Celsius
    output wire [1:0] state,       // voted state
    output wire       admit,       // input may be accepted this cycle
    output wire       repair       // copies disagree now; rewritten at the next edge
);

    localparam [1:0] S_NORMAL   = 2'd0;
    localparam [1:0] S_THROTTLE = 2'd1;
    localparam [1:0] S_STOP     = 2'd2;

    wire [1:0] c0, c1, c2;
    wire [1:0] voted = (c0 & c1) | (c1 & c2) | (c0 & c2);

    wire signed [7:0] t = temp_c;

    reg [1:0] nxt;
    always @* begin
        if (!temp_valid || t >= T_STOP) begin
            nxt = S_STOP;
        end else begin
            case (voted)
                S_NORMAL:   nxt = (t >= T_THROTTLE) ? S_THROTTLE : S_NORMAL;
                S_THROTTLE: nxt = (t <= T_RECOVER)  ? S_NORMAL   : S_THROTTLE;
                // S_STOP, and the unused encoding 2'b11 treated as STOP.
                default:    nxt = (t <= T_RECOVER)  ? S_NORMAL   : S_STOP;
            endcase
        end
    end

    orbit_keep_reg #(.W(2), .RESET_VAL(S_STOP)) u_copy0 (
        .clk(clk), .rst_n(rst_n), .en(1'b1), .d(nxt), .q(c0)
    );

    orbit_keep_reg #(.W(2), .RESET_VAL(S_STOP)) u_copy1 (
        .clk(clk), .rst_n(rst_n), .en(1'b1), .d(nxt), .q(c1)
    );

    orbit_keep_reg #(.W(2), .RESET_VAL(S_STOP)) u_copy2 (
        .clk(clk), .rst_n(rst_n), .en(1'b1), .d(nxt), .q(c2)
    );

    // Alternate-cycle admission while throttled. The first THROTTLE cycle
    // admits, the next does not, and so on.
    reg phase;
    always @(posedge clk) begin
        if (!rst_n)
            phase <= 1'b0;
        else
            phase <= (voted == S_THROTTLE) ? ~phase : 1'b0;
    end

    assign state  = voted;
    assign admit  = (voted == S_NORMAL) | ((voted == S_THROTTLE) & ~phase);
    assign repair = (c0 != c1) | (c1 != c2);

endmodule

`default_nettype wire
