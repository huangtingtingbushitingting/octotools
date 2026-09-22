module multi_pipe_8bit (
    input clk,
    input rst_n,
    input mul_en_in,
    input [7:0] mul_a,
    input [7:0] mul_b,
    output reg mul_en_out,
    output reg [15:0] mul_out
);

    // Input registers and enable pipeline
    reg mul_en_out_reg;
    reg [7:0] mul_a_reg;
    reg [7:0] mul_b_reg;

    // Partial product generation
    wire [7:0] temp [0:7];
    genvar i;
    generate
        for (i = 0; i < 8; i = i + 1) begin : gen_partial
            assign temp[i] = mul_b_reg[i] ? mul_a_reg : 8'd0;
        end
    endgenerate

    // Partial sum registers
    reg [15:0] sum [0:7];
    reg [15:0] mul_out_reg;

    // Input control and registers
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            mul_en_out_reg <= 1'b0;
            mul_a_reg <= 8'd0;
            mul_b_reg <= 8'd0;
        end else begin
            mul_en_out_reg <= mul_en_in;
            if (mul_en_in) begin
                mul_a_reg <= mul_a;
                mul_b_reg <= mul_b;
            end
        end
    end

    // Partial sum calculation
    integer j;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (j = 0; j < 8; j = j + 1) begin
                sum[j] <= 16'd0;
            end
            mul_out_reg <= 16'd0;
        end else begin
            // First stage: shift and add
            sum[0] <= temp[0];
            for (j = 1; j < 8; j = j + 1) begin
                sum[j] <= sum[j-1] + temp[j];
            end
            // Final sum accumulation
            mul_out_reg <= sum[7];
        end
    end

    // Output assignment
    always @(*) begin
        if (mul_en_out) begin
            mul_out = mul_out_reg;
        end else begin
            mul_out = 16'd0;
        end
    end

endmodule
