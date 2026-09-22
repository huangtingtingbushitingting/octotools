module multi_pipe_4bit #(
    parameter size = 4
) (
    input clk,
    input rst_n,
    input [size-1:0] mul_a,
    input [size-1:0] mul_b,
    output reg [2*size-1:0] mul_out
);

    // Extended inputs with zero padding
    wire [2*size-1:0] a_extended = {size{1'b0}, mul_a};
    wire [2*size-1:0] b_extended = {size{1'b0}, mul_b};

    // Partial products
    reg [2*size-1:0] partial_products [0:size-1];
    reg [2*size-1:0] sum_reg [0:size-1];
    reg [2*size-1:0] total_sum;

    // Generate block for partial products
    generate
        genvar i;
        for (i = 0; i < size; i = i + 1) begin : gen_partial
            always @(*) begin
                if (b_extended[i]) begin
                    partial_products[i] = a_extended << i;
                end else begin
                    partial_products[i] = 0;
                end
            end
        end
    endgenerate

    // Sum registers
    integer j;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (j = 0; j < size; j = j + 1) begin
                sum_reg[j] <= 0;
            end
            total_sum <= 0;
        end else begin
            // Accumulate partial products with pipeline stages
            sum_reg[0] <= partial_products[0];
            for (j = 1; j < size; j = j + 1) begin
                sum_reg[j] <= sum_reg[j-1] + partial_products[j];
            end
            total_sum <= sum_reg[size-1];
        end
    end

    // Final product calculation
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            mul_out <= 0;
        end else begin
            mul_out <= total_sum;
        end
    end

endmodule
