module pe (
    input clk,
    input rst,
    input signed [31:0] a,
    input signed [31:0] b,
    output reg signed [31:0] c
);

    // Accumulator register
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            c <= 32'd0;
        end else begin
            c <= c + (a * b);
        end
    end

endmodule
