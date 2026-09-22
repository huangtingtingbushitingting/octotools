module freq_divbyfrac (
    input clk,
    input rst_n,
    output clk_div
);

    reg [2:0] counter;
    reg clk_div_pos, clk_div_neg;

    // Counter increments on every clock edge (both edges)
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            counter <= 3'd0;
            clk_div_pos <= 1'b0;
        end else begin
            if (counter == 3'd6) begin
                counter <= 3'd0;
                clk_div_pos <= 1'b1;
            end else begin
                counter <= counter + 1;
                clk_div_pos <= 1'b0;
            end
        end
    end

    // Counter for negative edge
    always @(negedge clk or negedge rst_n) begin
        if (!rst_n) begin
            clk_div_neg <= 1'b0;
        end else begin
            if (counter == 3'd6) begin
                clk_div_neg <= 1'b1;
            end else begin
                clk_div_neg <= 1'b0;
            end
        end
    end

    // Adjust duty cycle by OR-ing both edges
    assign clk_div = clk_div_pos | clk_div_neg;

endmodule
