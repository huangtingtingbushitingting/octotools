module TopModule (
    input clk,
    input async_reset_n,
    input enable,
    output reg [3:0] count
);

always @(posedge clk or negedge async_reset_n) begin
    if (!async_reset_n) begin
        count <= 4'b0;
    end else begin
        if (enable) begin
            if (count == 4'd9) begin
                count <= 4'b0;
            end else begin
                count <= count + 1;
            end
        end
    end
end

endmodule
