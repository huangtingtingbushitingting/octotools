module TopModule (
    input wire a,
    input wire b,
    input wire sel,
    output wire y
);

    assign y = (sel == 1'b0) ? a : b;

endmodule
