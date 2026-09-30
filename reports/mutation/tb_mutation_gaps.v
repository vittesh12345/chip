// Evidence bench for reports/mutation/summary.md (mutation area, not part of
// any test suite): each check below is one the suite lacks, and each kills
// one or more mutants that survive `make mutation`. Run by `make mutation-gaps`.
// T1: fault_q 0->1 upset while a result is held -> fault must stay high,
//     out_valid and in_ready low, until clear_fault (SPEC 4, 5: sticky, masked).
// T2: res_b upset while a result is held -> out_data keeps copy A (SPEC 5).
// T3: two thermal copies upset to code 3 -> voted 3 behaves as STOP:
//     shutdown_req high, in_ready low (SPEC 2, 6).
// T4 (two upsets, outside the single-fault model; only run with +t4):
//     fault_q 0->1 while a result is offered with out_ready high, then
//     fault_q 1->0: the held result must be presented again.
`timescale 1ns/1ps
module tb_mutation_gaps;
    reg clk = 0, rst_n = 0, in_valid = 0, in_first = 0, in_last = 0, out_ready = 0;
    reg temp_valid = 1, clear_fault = 0;
    reg [7:0] temp_c = 8'sd25;
    reg [31:0] in_a = 0, in_b = 0;
    wire in_ready, out_valid, fault, therm_repair, shutdown_req;
    wire [127:0] out_data;
    wire [1:0] therm_state;
    integer errors = 0, k;
    orbit_demo dut (.clk(clk), .rst_n(rst_n), .in_valid(in_valid), .in_ready(in_ready),
        .in_first(in_first), .in_last(in_last), .in_a(in_a), .in_b(in_b),
        .out_valid(out_valid), .out_ready(out_ready), .out_data(out_data),
        .temp_valid(temp_valid), .temp_c(temp_c), .clear_fault(clear_fault), .fault(fault),
        .therm_state(therm_state), .therm_repair(therm_repair), .shutdown_req(shutdown_req));
    always #5 clk = ~clk;

    task one_result;   // single-term sum 3*5 in every lane, left in the buffer
        begin
            in_a = {4{8'd3}}; in_b = {4{8'd5}}; in_first = 1; in_last = 1; in_valid = 1;
            @(posedge clk); while (!in_ready) @(posedge clk);
            #1 in_valid = 0; in_first = 0; in_last = 0;
            @(posedge clk); #1;
            if (!out_valid) begin errors = errors + 1; $display("ERR no result"); end
        end
    endtask

    task do_clear;
        begin
            @(negedge clk) clear_fault = 1; @(negedge clk) clear_fault = 0; @(posedge clk); #1;
        end
    endtask

    initial begin
        repeat (3) @(posedge clk); #1 rst_n = 1;
        repeat (3) @(posedge clk); #1;          // STOP -> NORMAL (25 C)
        // T1
        one_result;
        @(negedge clk) dut.fault_q = 1'b1;      // SEU away from the active edge
        for (k = 0; k < 6; k = k + 1) begin
            @(posedge clk); #1;
            if (!fault || out_valid || in_ready) begin
                errors = errors + 1;
                $display("ERR T1 cycle %0d: fault=%b out_valid=%b in_ready=%b", k, fault, out_valid, in_ready);
            end
        end
        do_clear;
        // T2
        one_result;
        @(negedge clk) dut.g_lane[0].u_lane.u_res_b.q[4] = ~dut.g_lane[0].u_lane.u_res_b.q[4];
        #1 if (out_valid || out_data[31:0] !== 32'd15) begin
            errors = errors + 1;
            $display("ERR T2: out_valid=%b out_data[31:0]=%0d (copy A holds 15)", out_valid, out_data[31:0]);
        end
        do_clear;
        // T3
        in_valid = 1; in_first = 1; in_last = 0;
        @(negedge clk) begin dut.u_thermal.u_copy0.q = 2'b11; dut.u_thermal.u_copy1.q = 2'b11; end
        #1 if (therm_state !== 2'd3 || !shutdown_req || in_ready) begin
            errors = errors + 1;
            $display("ERR T3: therm_state=%0d shutdown_req=%b in_ready=%b", therm_state, shutdown_req, in_ready);
        end
        in_valid = 0;
        if ($test$plusargs("t4")) begin
            repeat (4) @(posedge clk); #1;        // thermal copies repaired, NORMAL again
            one_result;
            @(negedge clk) begin dut.fault_q = 1'b1; out_ready = 1; end
            repeat (2) @(posedge clk);
            @(negedge clk) begin dut.fault_q = 1'b0; out_ready = 0; end
            #1 if (!out_valid || out_data[31:0] !== 32'd15) begin
                errors = errors + 1;
                $display("ERR T4: out_valid=%b after fault_q 1->0 (held result lost)", out_valid);
            end
        end
        $display("TB_MUTATION_GAPS %s (%0d errors)", errors ? "FAIL" : "PASS", errors);
        $finish;
    end
endmodule
