module adder_pipe_64bit (
    input clk,
    input rst_n,
    input i_en,
    input [63:0] adda,
    input [63:0] addb,
    output reg [64:0] result,
    output reg o_en
);

    // Define pipeline stages
    localparam STAGES = 3; // Example pipeline stages; adjust as needed

    // Internal registers for pipeline stages
    reg [63:0] a_reg [0:STAGES];
    reg [63:0] b_reg [0:STAGES];
    reg en_reg [0:STAGES];
    reg [64:0] sum_reg [0:STAGES];

    // Initialize pipeline registers
    integer i;
    initial begin
        for (i = 0; i <= STAGES; i = i + 1) begin
            a_reg[i] = 64'b0;
            b_reg[i] = 64'b0;
            en_reg[i] = 1'b0;
            sum_reg[i] = 65'b0;
        end
    end

    // Pipeline stage assignments
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Reset all pipeline registers
            for (i = 0; i <= STAGES; i = i + 1) begin
                a_reg[i] <= 64'b0;
                b_reg[i] <= 64'b0;
                en_reg[i] <= 1'b0;
                sum_reg[i] <= 65'b0;
            end
        end else begin
            // First stage: input registers
            a_reg[0] <= adda;
            b_reg[0] <= addb;
            en_reg[0] <= i_en;

            // Subsequent stages: propagate through pipeline
            for (i = 1; i <= STAGES; i = i + 1) begin
                a_reg[i] <= a_reg[i-1];
                b_reg[i] <= b_reg[i-1];
                en_reg[i] <= en_reg[i-1];
                // Calculate sum with carry
                sum_reg[i] <= {1'b0, a_reg[i-1]} + {1'b0, b_reg[i-1]} + sum_reg[i-1][64];
            end
        end
    end

    // Output assignment
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            result <= 65'b0;
            o_en <= 1'b0;
        end else begin
            // The final sum is in the last stage
            result <= sum_reg[STAGES];
            o_en <= en_reg[STAGES];
        end
    end

endmodule
