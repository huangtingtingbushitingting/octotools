module adder_32bit (
    input [32:1] A,
    input [32:1] B,
    output [32:1] S,
    output C32
);

    wire [16:0] carry;

    // Instantiate two 16-bit CLA blocks
    cla_16bit cla_low (
        .A(A[16:1]),
        .B(B[16:1]),
        .S(S[16:1]),
        .Cin(1'b0),
        .Cout(carry[16])
    );

    cla_16bit cla_high (
        .A(A[32:17]),
        .B(B[32:17]),
        .S(S[32:17]),
        .Cin(carry[16]),
        .Cout(C32)
    );

endmodule

// 16-bit Carry-Lookahead Adder module
module cla_16bit (
    input [16:1] A,
    input [16:1] B,
    output [16:1] S,
    input Cin,
    output Cout
);

    wire [15:0] G, P;
    wire [16:0] carry;

    assign carry[0] = Cin;

    // Generate and propagate for each bit
    genvar i;
    generate
        for (i = 1; i <= 16; i = i + 1) begin : gen_pp
            assign G[i-1] = A[i] & B[i];
            assign P[i-1] = A[i] | B[i];
        end
    endgenerate

    // Carry Lookahead Logic
    generate
        for (i = 1; i <= 16; i = i + 1) begin : cla_logic
            assign carry[i] = G[i-1] | (P[i-1] & carry[i-1]);
        end
    endgenerate

    // Sum calculation
    assign S[16:1] = A[16:1] ^ B[16:1] ^ carry[16:1];
    assign Cout = carry[16];

endmodule
