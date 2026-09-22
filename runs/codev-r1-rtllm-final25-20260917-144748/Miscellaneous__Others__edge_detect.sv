module edge_detect (
    input clk,
    input rst_n,
    input a,
    output reg rise,
    output reg down
);

    reg a_prev;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            a_prev <= 1'b0;
            rise <= 1'b0;
            down <= 1'b0;
        end else begin
            a_prev <= a;
            // Detect rising edge: current a is 1 and previous was 0
            rise <= (a & ~a_prev);
            // Detect falling edge: current a is 0 and previous was 1
            down <= (~a & a_prev);
        end
    end

endmodule
