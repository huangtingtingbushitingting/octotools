module RAM (
    input clk,
    input rst_n,
    input write_en,
    input [2:0] write_addr,
    input [5:0] write_data,
    input read_en,
    input [2:0] read_addr,
    output reg [5:0] read_data
);

    parameter WIDTH = 6;
    parameter DEPTH = 8;
    reg [WIDTH-1:0] ram [0:DEPTH-1];

    // Initialize RAM to all zeros
    integer i;
    initial begin
        for (i = 0; i < DEPTH; i = i + 1) begin
            ram[i] = 6'b000000;
        end
    end

    // Write operation
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Reset all memory locations to 0
            for (i = 0; i < DEPTH; i = i + 1) begin
                ram[i] <= 6'b000000;
            end
        end else begin
            if (write_en) begin
                ram[write_addr] <= write_data;
            end
        end
    end

    // Read operation
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            read_data <= 6'b000000;
        end else begin
            if (read_en) begin
                read_data <= ram[read_addr];
            end else begin
                read_data <= 6'b000000;
            end
        end
    end

endmodule
