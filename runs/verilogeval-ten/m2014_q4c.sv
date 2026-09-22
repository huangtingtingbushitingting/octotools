module d_ff_sync_reset (
    input logic clk,
    input logic rst,
    input logic d,
    output logic q
);

    always_ff @(posedge clk) begin
        if (rst)
            q <= 0;
        else
            q <= d;
    end

endmodule
