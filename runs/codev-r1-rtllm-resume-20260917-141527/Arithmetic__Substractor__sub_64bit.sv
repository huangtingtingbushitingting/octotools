module sub_64bit (
    input signed [63:0] A,
    input signed [63:0] B,
    output signed [63:0] result,
    output overflow
);

    // Perform subtraction
    assign result = A - B;

    // Overflow detection logic
    // Overflow occurs if the signs of A and B are different and the sign of the result is different from A's sign
    // Positive overflow: A is positive (A[63] == 0), B is negative (B[63] == 1), result is negative (result[63] == 1)
    // Negative overflow: A is negative (A[63] == 1), B is positive (B[63] == 0), result is positive (result[63] == 0)
    wire a_sign = A[63];
    wire b_sign = B[63];
    wire result_sign = result[63];

    assign overflow = (a_sign == 0 && b_sign == 1 && result_sign == 1) || // Positive overflow condition
                      (a_sign == 1 && b_sign == 0 && result_sign == 0); // Negative overflow condition

endmodule
