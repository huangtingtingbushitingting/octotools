module div_16bit (
    input [15:0] A,
    input [7:0] B,
    output reg [15:0] result,
    output reg [15:0] odd
);

    reg [15:0] a_reg;
    reg [7:0] b_reg;
    integer i;

    // Combinational block for a_reg and b_reg
    always @(*) begin
        a_reg = A;
        b_reg = B;
    end

    // Combinational block for division logic
    always @(*) begin
        result = 16'b0;
        odd = 16'b0;
        if (b_reg == 0) begin
            // Handle division by zero if needed, but per spec, assume B is non-zero
            result = 16'b0;
            odd = 16'b0;
        end else begin
            for (i = 15; i >= 0; i = i - 1) begin
                // Shift the remainder left by 1 bit
                odd = {odd[14:0], a_reg[15]};
                a_reg = {a_reg[14:0], 1'b0}; // Shift left the dividend

                // Compare the current remainder with divisor
                if (odd >= b_reg) begin
                    result[i] = 1'b1;
                    odd = odd - b_reg;
                end else begin
                    result[i] = 1'b0;
                end
            end
        end
    end

endmodule
