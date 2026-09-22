module accu (
    input clk,
    input rst_n,
    input [7:0] data_in,
    input valid_in,
    output reg valid_out,
    output reg [9:0] data_out
);

    reg [1:0] count;
    reg [9:0] sum;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= 2'b00;
            sum <= 10'b0;
            valid_out <= 1'b0;
        end else begin
            if (valid_in) begin
                sum <= sum + data_in;
                count <= count + 1;
                if (count == 2'd3) begin
                    valid_out <= 1'b1;
                    data_out <= sum + data_in; // Add the current data_in to the sum
                    count <= 2'b00;
                    sum <= 10'b0;
                end else begin
                    valid_out <= 1'b0;
                end
            end else begin
                valid_out <= 1'b0;
            end
        end
    end

endmodule
