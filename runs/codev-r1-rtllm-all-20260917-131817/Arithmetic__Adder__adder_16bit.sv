module adder_16bit (
    input [15:0] a,
    input [15:0] b,
    input Cin,
    output [15:0] y,
    output Co
);

    // Instantiate two 8-bit adders
    wire carry_mid; // Carry from the first 8-bit adder to the second

    // First 8-bit adder (lower bits)
    adder_8bit lower_adder (
        .a(a[7:0]),
        .b(b[7:0]),
        .cin(Cin),
        .sum(y[7:0]),
        .cout(carry_mid)
    );

    // Second 8-bit adder (upper bits)
    adder_8bit upper_adder (
        .a(a[15:8]),
        .b(b[15:8]),
        .cin(carry_mid),
        .sum(y[15:8]),
        .cout(Co)
    );

endmodule

// 8-bit adder module
module adder_8bit (
    input [7:0] a,
    input [7:0] b,
    input cin,
    output [7:0] sum,
    output cout
);

    // Instantiate two 4-bit adders
    wire carry_mid;

    // First 4-bit adder (lower nibble)
    adder_4bit lower_adder (
        .a(a[3:0]),
        .b(b[3:0]),
        .cin(cin),
        .sum(sum[3:0]),
        .cout(carry_mid)
    );

    // Second 4-bit adder (upper nibble)
    adder_4bit upper_adder (
        .a(a[7:4]),
        .b(b[7:4]),
        .cin(carry_mid),
        .sum(sum[7:4]),
        .cout(cout)
    );

endmodule

// 4-bit adder module
module adder_4bit (
    input [3:0] a,
    input [3:0] b,
    input cin,
    output [3:0] sum,
    output cout
);

    // Instantiate two 2-bit adders
    wire carry_mid;

    // First 2-bit adder (lower half)
    adder_2bit lower_adder (
        .a(a[1:0]),
        .b(b[1:0]),
        .cin(cin),
        .sum(sum[1:0]),
        .cout(carry_mid)
    );

    // Second 2-bit adder (upper half)
    adder_2bit upper_adder (
        .a(a[3:2]),
        .b(b[3:2]),
        .cin(carry_mid),
        .sum(sum[3:2]),
        .cout(cout)
    );

endmodule

// 2-bit adder module
module adder_2bit (
    input [1:0] a,
    input [1:0] b,
    input cin,
    output [1:0] sum,
    output cout
);

    // Instantiate two 1-bit adders
    wire carry_mid;

    // First 1-bit adder (LSB)
    adder_1bit bit0 (
        .a(a[0]),
        .b(b[0]),
        .cin(cin),
        .sum(sum[0]),
        .cout(carry_mid)
    );

    // Second 1-bit adder (next bit)
    adder_1bit bit1 (
        .a(a[1]),
        .b(b[1]),
        .cin(carry_mid),
        .sum(sum[1]),
        .cout(cout)
    );

endmodule

// 1-bit adder module
module adder_1bit (
    input a,
    input b,
    input cin,
    output sum,
    output cout
);

    assign {cout, sum} = a + b + cin;

endmodule
