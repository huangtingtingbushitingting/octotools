module adder_bcd (
    input [3:0] A,
    input [3:0] B,
    input Cin,
    output [3:0] Sum,
    output Cout
);

    wire [3:0] bin_sum;
    wire [4:0] temp_sum;

    // Binary addition of A, B, and Cin
    assign temp_sum = A + B + Cin;
    assign bin_sum = temp_sum[3:0];

    // BCD correction
    wire [3:0] corrected_sum;
    assign corrected_sum = (bin_sum > 4'd9) ? (bin_sum + 4'd6) : bin_sum;

    // Determine carry out
    assign Cout = (temp_sum > 5'd9) ? 1'b1 : 1'b0;

    // Assign outputs
    assign Sum = corrected_sum;

endmodule
