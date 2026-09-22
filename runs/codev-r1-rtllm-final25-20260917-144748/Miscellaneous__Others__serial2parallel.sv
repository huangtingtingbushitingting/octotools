module serial2parallel (
    input clk,
    input rst_n,
    input din_serial,
    input din_valid,
    output reg [7:0] dout_parallel,
    output reg dout_valid
);

    reg [3:0] cnt;
    reg [7:0] shift_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cnt <= 4'd0;
            shift_reg <= 8'd0;
            dout_parallel <= 8'd0;
            dout_valid <= 1'b0;
        end else begin
            if (din_valid) begin
                if (cnt == 4'd7) begin
                    // After receiving 8th bit, output on next cycle
                    dout_parallel <= shift_reg;
                    dout_valid <= 1'b1;
                    cnt <= 4'd0;
                    shift_reg <= {shift_reg[6:0], din_serial}; // Wait for next group
                end else begin
                    shift_reg <= {shift_reg[6:0], din_serial};
                    cnt <= cnt + 1;
                    dout_valid <= 1'b0;
                end
            end else begin
                dout_valid <= 1'b0;
                // If din_valid is low, retain current state
            end
        end
    end

endmodule
