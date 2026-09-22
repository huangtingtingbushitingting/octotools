module LIFObuffer (
    input wire [3:0] dataIn,
    input wire RW,
    input wire EN,
    input wire Rst,
    input wire Clk,
    output reg EMPTY,
    output reg FULL,
    output reg [3:0] dataOut
);

    reg [3:0] stack_mem [0:3]; // 4-entry stack memory
    reg [2:0] SP; // Stack Pointer (0 to 3, 4 indicates empty)

    // Initialize stack pointer to 4 (empty) on reset
    always @(posedge Clk) begin
        if (Rst) begin
            SP <= 3'd4; // 4 entries, so 4 means empty
            EMPTY <= 1'b1;
            FULL <= 1'b0;
            // Clear stack memory
            stack_mem[0] <= 4'b0;
            stack_mem[1] <= 4'b0;
            stack_mem[2] <= 4'b0;
            stack_mem[3] <= 4'b0;
        end
        else if (EN) begin
            // Update flags based on SP
            EMPTY <= (SP == 4);
            FULL <= (SP == 0);

            if (!RW && !FULL) begin // Write (push)
                stack_mem[SP] <= dataIn;
                SP <= SP - 1;
            end
            else if (RW && !EMPTY) begin // Read (pop)
                dataOut <= stack_mem[SP-1];
                stack_mem[SP-1] <= 4'b0; // Clear popped entry
                SP <= SP + 1;
            end
        end
    end

endmodule
