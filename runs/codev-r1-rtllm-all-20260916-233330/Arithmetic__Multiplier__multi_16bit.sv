module multi_16bit (
    input clk,
    input rst_n,
    input start,
    input [15:0] ain,
    input [15:0] bin,
    output reg [31:0] yout,
    output reg done
);

    reg [15:0] areg, breg;
    reg [4:0] i; // Since i can go up to 17, 5 bits needed (0-16)
    reg [31:0] yout_r;
    reg done_r;

    // Update shift count register (i)
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            i <= 5'd0;
        end else begin
            if (start) begin
                if (i < 5'd17)
                    i <= i + 5'd1;
                else
                    i <= i; // Hold once reaches 17
            end else begin
                i <= 5'd0;
            end
        end
    end

    // Update done_r
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            done_r <= 1'b0;
        end else begin
            if (i == 5'd16)
                done_r <= 1'b1;
            else if (i == 5'd17)
                done_r <= 1'b0;
            else
                done_r <= done_r;
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
                if (i == 5'd0) begin
                    areg <= ain;
                    breg <= bin;
                    yout_r <= 32'd0;
                end else if (i > 5'd0 && i < 5'd17) begin
                    if (areg[i-1]) begin
                        yout_r <= yout_r + (breg << (i-1));
                    end
                end
            end else begin
                areg <= 16'd0;
                breg <= 16'd0;
                yout_r <= 32'd0;
            end
        end
    end

    // Assign outputs
    always @* begin
        done = done_r;
        yout = yout_r;
    end

endmodule
