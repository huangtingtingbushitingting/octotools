module mux_2_1 (
    input logic a,
    input logic b,
    input logic sel,
    output logic y
);

    always_comb begin
        if (sel == 1'b0) begin
            y = a;
        end else begin
            y = b;
        end
    end

endmodule
