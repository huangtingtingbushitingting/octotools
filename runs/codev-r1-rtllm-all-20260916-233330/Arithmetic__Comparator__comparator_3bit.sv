module comparator_3bit (
    input [2:0] A,
    input [2:0] B,
    output A_greater,
    output A_equal,
    output A_less
);

    // Compare each bit starting from the most significant bit (MSB)
    wire [2:0] A_gt_B;
    wire [2:0] A_lt_B;

    // MSB comparison
    assign A_gt_B[2] = (A[2] & ~B[2]);
    assign A_lt_B[2] = (~A[2] & B[2]);

    // Middle bit comparison (only if MSBs are equal)
    assign A_gt_B[1] = (~A_gt_B[2] & ~A_lt_B[2] & (A[1] & ~B[1]));
    assign A_lt_B[1] = (~A_gt_B[2] & ~A_lt_B[2] & (~A[1] & B[1]));

    // LSB comparison (only if higher bits are equal)
    assign A_gt_B[0] = (~A_gt_B[2] & ~A_lt_B[2] & ~A_gt_B[1] & ~A_lt_B[1] & (A[0] & ~B[0]));
    assign A_lt_B[0] = (~A_gt_B[2] & ~A_lt_B[2] & ~A_gt_B[1] & ~A_lt_B[1] & (~A[0] & B[0]));

    // Equal when all bits are equal
    assign A_equal = (A == B);

    // Determine the greater and less based on the highest differing bit
    assign A_greater = (A_gt_B[2] | A_gt_B[1] | A_gt_B[0]);
    assign A_less = (A_lt_B[2] | A_lt_B[1] | A_lt_B[0]);

endmodule
