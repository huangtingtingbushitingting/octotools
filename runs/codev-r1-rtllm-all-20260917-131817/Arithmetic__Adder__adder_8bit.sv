module adder_8bit (
    input [7:0] a,
    input [7:0] b,
    input cin,
    output [7:0] sum,
    output cout
);

    wire [7:0] c; // Carry between each full adder

    // First full adder handles the carry-in
    full_adder fa0(
        .a(a[0]),
        .b(b[0]),
        .cin(cin),
        .sum(sum[0]),
        .cout(c[0])
    );

    // Generate the remaining 7 full adders
    genvar i;
    generate
        for (i = 1; i < 8; i = i + 1) begin : adder_loop
            full_adder fa(
                .a(a[i]),
                .b(b[i]),
                .cin(c[i-1]),
                .sum(sum[i]),
                .cout(c[i])
            );
        end
    endgenerate

    // The final carry out is the last carry
    assign cout = c[7];

endmodule

// Full adder module
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
