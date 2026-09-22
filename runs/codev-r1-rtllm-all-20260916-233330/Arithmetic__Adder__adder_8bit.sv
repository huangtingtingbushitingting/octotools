module adder_8bit (
    input [7:0] a,
    input [7:0] b,
    input cin,
    output [7:0] sum,
    output cout
);

    wire [7:0] c; // Carry between stages

    // Instantiate 8 full adders
    full_adder fa0(
        .a(a[0]),
        .b(b[0]),
        .cin(cin),
        .sum(sum[0]),
        .cout(c[0])
    );

    genvar i;
    generate
        for (i = 1; i < 8; i = i + 1) begin : gen_full_adders
            full_adder fa(
                .a(a[i]),
                .b(b[i]),
                .cin(c[i-1]),
                .sum(sum[i]),
                .cout(c[i])
            );
        end
    endgenerate

    assign cout = c[7];

endmodule

module full_adder (
    input a,
    input b,
    input cin,
    output sum,
    output cout
);

    assign sum = a ^ b ^ cin;
    assign cout = (a & b) | (a & cin) | (b & cin);

endmodule
