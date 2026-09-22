module serial_2s_complementer (
    input wire clk,
    input wire reset,
    input wire x,
    output reg Z
);

    reg carry;

    always @(posedge clk or posedge reset) begin
        if (reset) begin
            Z <= 0;
            carry <= 0;
        end else begin
            if (carry) begin
                Z <= ~x;
                carry <= ~x;
            end else begin
                Z <= x;
                carry <= x;
            end
        end
    end

endmodule
