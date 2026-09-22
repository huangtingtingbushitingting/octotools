module adder_bcd (
    input [3:0] A,
    input [3:0] B,
    input Cin,
    output [3:0] Sum,
    output Cout
);

    wire [3:0] bin_sum;
    wire [4:0] temp_sum;
    wire correction;

    // Binary addition of A, B, and Cin
    assign temp_sum = A + B + Cin;
    assign bin_sum = temp_sum[3:0];
    assign correction = (temp_sum > 9) ? 1 : 0;

    // BCD correction: add 6 if sum exceeds 9
    wire [3:0] corrected_sum;
    assign corrected_sum = bin_sum + (correction ? 4'd6 : 4'd0);

    // Determine the final sum and carry out
    assign Sum = (corrected_sum > 9) ? corrected_sum : (correction ? corrected_sum : bin_sum);
    assign Cout = (temp_sum > 9) ? 1 : 0;

endmodule
