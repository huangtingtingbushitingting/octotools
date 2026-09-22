module next_state_y2 (
    input logic clk,
    input logic rst_n,
    input logic x,
    input logic [2:0] y,
    output logic Y2
);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            Y2 <= 1'b0;
        end else begin
            case (y)
                3'b000: Y2 <= 1'b0; // State A
                3'b001: Y2 <= x ? 1'b0 : 1'b1; // State B
                3'b010: Y2 <= 1'b1; // State C
                3'b011: Y2 <= 1'b1; // State D
                3'b100: Y2 <= x ? 1'b1 : 1'b1; // State E
                3'b101: Y2 <= x ? 1'b1 : 1'b0; // State F
                default: Y2 <= 1'b0;
            endcase
        end
    end

endmodule
