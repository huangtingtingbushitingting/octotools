module multi_booth_8bit (
    input clk,
    input reset,
    input [7:0] a,
    input [7:0] b,
    output reg [15:0] p,
    output reg rdy
);

    reg [15:0] multiplicand;
    reg [15:0] multiplier;
    reg [4:0] ctr;

    always @(posedge clk or posedge reset) begin
        if (reset) begin
            // Initialize registers on reset
            multiplicand <= {{8{a[7]}}, a};
            multiplier <= {{8{b[7]}}, b};
            ctr <= 5'd0;
            p <= 16'd0;
            rdy <= 1'b0;
        end else begin
            if (ctr < 16) begin
                // Booth algorithm steps
                // Check current and previous bits (Booth encoding)
                // Since Booth uses pairs, but in Radix-4, we look at two bits and one previous bit
                // However, the original code provided in the problem statement may have a simplified approach
                // Here, the code uses a counter and shifts multiplicand left each step
                // The actual Booth algorithm steps may need adjustment, but per the user's description:

                // Left shift multiplicand by 1 each iteration
                multiplicand <= multiplicand << 1;

                // Check if current bit (ctr) is 1 (Booth encoding)
                if (multiplier[ctr]) begin
                    p <= p + multiplicand;
                end

                ctr <= ctr + 1;
                rdy <= 1'b0;
            end else begin
                // Multiplication complete
                rdy <= 1'b1;
            end
        end
    end

endmodule
