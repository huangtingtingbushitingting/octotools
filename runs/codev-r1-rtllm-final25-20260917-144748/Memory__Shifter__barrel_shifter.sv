module barrel_shifter (
    input [7:0] in,
    input [2:0] ctrl,
    output [7:0] out
);

    // Internal wires for each stage
    wire [7:0] stage0, stage1, stage2;

    // Stage 0: Shift by 4 if ctrl[2] is set
    assign stage0 = ctrl[2] ? {4'b0, in[7:4]} : in;

    // Stage 1: Shift stage0 by 2 if ctrl[1] is set
    assign stage1 = ctrl[1] ? {2'b0, stage0[7:2]} : stage0;

    // Stage 2: Shift stage1 by 1 if ctrl[0] is set
    assign stage2 = ctrl[0] ? {1'b0, stage1[7:1]} : stage1;

    assign out = stage2;

endmodule
