module sequential_circuit (
    input logic clk,
    input logic a,
    output logic q
);
    always_ff @(posedge clk) begin
        if (a == 1'b1) begin
            q <= ~q;
        end else begin
            q <= 1'b1;
        end
    end
endmodule
