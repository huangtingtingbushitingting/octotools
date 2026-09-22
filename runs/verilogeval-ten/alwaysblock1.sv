module and_gate (
    input wire a,
    input wire b,
    output wire y_assign,
    output wire y_always
);

    // Using assign statement
    assign y_assign = a & b;

    // Using combinational always block
    reg y_temp;
    always @* begin
        y_temp = a & b;
    end

    // Assigning the result of the always block to the output
    assign y_always = y_temp;

endmodule
