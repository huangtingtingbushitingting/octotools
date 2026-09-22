module fixed_point_adder #(
    parameter Q = 16, // Number of fractional bits
    parameter N = 32  // Total bits (including integer and fractional)
) (
    input  [N-1:0] a,
    input  [N-1:0] b,
    output [N-1:0] c
);

    reg [N-1:0] res;

    // Determine the sign bits of a and b
    wire a_sign = a[N-1];
    wire b_sign = b[N-1];

    // Compute absolute values of a and b
    wire [N-1:0] a_abs = a_sign ? (~a + 1) : a;
    wire [N-1:0] b_abs = b_sign ? (~b + 1) : b;

    // Determine if signs are the same
    wire same_sign = (a_sign == b_sign);

    // Absolute value addition
    wire [N-1:0] sum_abs;
    wire carry;
    assign {carry, sum_abs} = a_abs + b_abs;

    // Absolute value subtraction
    wire [N-1:0] sub_abs;
    wire sub_borrow;
    assign {sub_borrow, sub_abs} = a_abs - b_abs;

    // Compare absolute values when signs differ
    wire a_gt_b = (a_abs > b_abs);

    // Determine result based on sign and comparison
    always @* begin
        if (same_sign) begin
            // Both positive or both negative: add absolute values
            res = {a_sign, sum_abs};
            // Check for overflow (carry out)
            if (carry) begin
                // Overflow in addition: saturate to maximum value
                res = a_sign ? {1'b1, {(N-1){1'b0}}} : {1'b0, {(N-1){1'b1}}};
            end
        end else begin
            // Signs differ: subtract smaller from larger
            if (a_gt_b) begin
                res = {1'b0, sub_abs};
            end else begin
                res = {b_sign, sub_abs};
            end
        end
    end

    // Assign output
    assign c = res;

endmodule
