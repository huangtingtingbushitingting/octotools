module fixed_point_subtractor #(
    parameter Q = 8,  // Number of fractional bits
    parameter N = 16  // Total bits (integer + fractional)
) (
    input  [N-1:0] a,
    input  [N-1:0] b,
    output [N-1:0] c
);

    reg [N-1:0] res;

    // Sign bits extraction
    wire sign_a = a[N-1];
    wire sign_b = b[N-1];

    // Magnitude of a and b
    wire [N-1:0] a_mag = sign_a ? -a : a;
    wire [N-1:0] b_mag = sign_b ? -b : b;

    // Determine operation based on signs
    always @* begin
        if (sign_a == sign_b) begin
            // Same sign subtraction
            res = a - b;
        end else begin
            // Different signs: add magnitudes
            if (a_mag > b_mag) begin
                res = a - b;
            end else if (b_mag > a_mag) begin
                res = b - a;
                // Swap signs if necessary
                res[N-1] = ~res[N-1];
            end else begin
                // Equal magnitudes, result is zero
                res = 0;
            end
        end

        // Handle zero case explicitly
        if (res == 0) begin
            res[N-1] = 0; // Ensure sign is positive
        end
    end

    assign c = res;

endmodule
