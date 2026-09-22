module adder_16bit (
    input [15:0] a,
    input [15:0] b,
    input Cin,
    output [15:0] y,
    output Co
);

    wire [7:0] carry;

    // Instantiate two 8-bit adders
    adder_8bit adder_low (
        .a(a[7:0]),
        .b(b[7:0]),
        .Cin(Cin),
        .y(y[7:0]),
        .Co(carry[0])
    );

    adder_8bit adder_high (
        .a(a[15:8]),
        .b(b[15:8]),
        .Cin(carry[0]),
        .y(y[15:8]),
        .Co(carry[1])
    );

    assign Co = carry[1];

endmodule

module adder_8bit (
    input [7:0] a,
    input [7:0] b,
    input Cin,
    output [7:0] y,
    output Co
);

    wire [7:0] sum;
    wire [8:0] carry;

    assign carry[0] = Cin;

    genvar i;
    generate
        for (i = 0; i < 8; i = i + 1) begin : adder_loop
            assign sum[i] = a[i] ^ b[i] ^ carry[i];
            assign carry[i+1] = (a[i] & b[i]) | (a[i] & carry[i]) | (b[i] & carry[i]);
        end
    endgenerate

    assign y = sum;
    assign Co = carry[8];

endmodule
