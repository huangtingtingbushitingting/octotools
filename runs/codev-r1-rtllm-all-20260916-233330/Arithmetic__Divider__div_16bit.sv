module div_16bit (
    input [15:0] A,
    input [7:0] B,
    output reg [15:0] result,
    output reg [15:0] odd
);

    reg [15:0] a_reg;
    reg [7:0] b_reg;

    always @(*) begin
        a_reg = A;
        b_reg = B;
    end

    always @(*) begin
        if (b_reg == 0) begin
            result = 16'hFFFF;
            odd = 16'hFFFF;
        end else begin
            result = 0;
            odd = 0;
            for (int i = 15; i >= 0; i--) begin
                if (i >= 8) begin
                    if (a_reg[i -: 8] >= b_reg) begin
                        result[i] = 1;
                        a_reg[i -: 8] = a_reg[i -: 8] - b_reg;
                    end else begin
                        result[i] = 0;
                    end
                end else begin
                    if (odd != 0) begin
                        odd = {odd[14:0], a_reg[i]};
                    end else begin
                        odd = {15'b0, a_reg[i]};
                    end
                end
            end
        end
    end

endmodule
