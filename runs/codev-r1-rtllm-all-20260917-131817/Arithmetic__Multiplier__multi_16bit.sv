module multi_16bit (
    input clk,
    input rst_n,
    input start,
    input [15:0] ain,
    input [15:0] bin,
    output reg [31:0] yout,
    output reg done
);

    reg [4:0] i; // Shift count register (0 to 16)
    reg [15:0] areg; // Multiplicand register
    reg [15:0] breg; // Multiplier register
    reg [31:0] yout_r; // Product register
    reg done_r;

    // Update shift count register (i)
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            i <= 5'd0;
        end else begin
            if (start && (i < 17)) begin
                i <= i + 1;
            end else if (!start) begin
                i <= 5'd0;
            end
        end
    end

    // Update done_r flag
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            done_r <= 1'b0;
        end else begin
            if (i == 16) begin
                done_r <= 1'b1;
            end else if (i == 17) begin
                done_r <= 1'b0;
            end
        end
    end

    // Shift and accumulate operation
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            areg <= 16'd0;
            breg <= 16'd0;
            yout_r <= 32'd0;
        end else begin
            if (start) begin
                if (i == 0) begin
                    areg <= ain;
                    breg <= bin;
                end else if (i > 0 && i < 17) begin
                    if (areg[i-1]) begin
                        yout_r <= yout_r + (breg << (i-1));
                    end
                end
            end
        end
    end

    // Output assignments
    always @(*) begin
        yout = yout_r;
        done = done_r;
    end

endmodule
