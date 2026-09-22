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
    localparam STAGES = 2; // Number of pipeline stages

    // Registers for pipeline stages
    reg [63:0] a_reg [0:STAGES];
    reg [63:0] b_reg [0:STAGES];
    reg [64:0] sum_reg [0:STAGES];
    reg [STAGES:0] en_reg;

    // Initialize pipeline registers
    integer i;
    initial begin
        for (i = 0; i <= STAGES; i = i + 1) begin
            a_reg[i] = 64'b0;
            b_reg[i] = 64'b0;
            sum_reg[i] = 65'b0;
        end
        en_reg = 0;
    end

    // Pipeline stage assignments
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Reset all pipeline registers
            for (i = 0; i <= STAGES; i = i + 1) begin
                a_reg[i] <= 64'b0;
                b_reg[i] <= 64'b0;
                sum_reg[i] <= 65'b0;
            end
            en_reg <= 0;
        end else begin
            // Shift data through pipeline stages
            en_reg <= {en_reg[STAGES-1:0], i_en};

            // Stage 0: Input registers
            a_reg[0] <= adda;
            b_reg[0] <= addb;

            // Subsequent stages: add and propagate carry
            for (i = 0; i < STAGES; i = i + 1) begin
                sum_reg[i+1] <= a_reg[i] + b_reg[i] + sum_reg[i][64];
                a_reg[i+1] <= a_reg[i];
                b_reg[i+1] <= b_reg[i];
            end

            // Final sum calculation
            sum_reg[0] <= a_reg[0] + b_reg[0];
        end
    end

    // Output assignment
    always @* begin
        result = sum_reg[STAGES];
        o_en = en_reg[STAGES];
    end

endmodule
