module adder_32bit (
    input [32:1] A,
    input [32:1] B,
    output [32:1] S,
    output C32
);

    // Instantiate four 8-bit CLA blocks
    wire [3:0] C_out;
    wire [3:0] G, P;

    // First 8-bit block (bits 1-8)
    cla_8bit cla1 (
        .A(A[8:1]),
        .B(B[8:1]),
        .S(S[8:1]),
        .C_in(1'b0),
        .C_out(C_out[0]),
        .G(G[0]),
        .P(P[0])
    );

    // Second 8-bit block (bits 9-16)
    cla_8bit cla2 (
        .A(A[16:9]),
        .B(B[16:9]),
        .S(S[16:9]),
        .C_in(C_out[0]),
        .C_out(C_out[1]),
        .G(G[1]),
        .P(P[1])
    );

    // Third 8-bit block (bits 17-24)
    cla_8bit cla3 (
        .A(A[24:17]),
        .B(B[24:17]),
        .S(S[24:17]),
        .C_in(C_out[1]),
        .C_out(C_out[2]),
        .G(G[2]),
        .P(P[2])
    );

    // Fourth 8-bit block (bits 25-32)
    cla_8bit cla4 (
        .A(A[32:25]),
        .B(B[32:25]),
        .S(S[32:25]),
        .C_in(C_out[2]),
        .C_out(C_out[3]),
        .G(G[3]),
        .P(P[3])
    );

    // Generate group propagate and generate signals
    wire [3:0] G_group;
    wire [3:0] P_group;

    // Compute group generate and propagate for each 8-bit block
    assign G_group[0] = G[0];
    assign P_group[0] = P[0];

    assign G_group[1] = G[1] | (P[1] & G_group[0]);
    assign P_group[1] = P[1] & P_group[0];

    assign G_group[2] = G[2] | (P[2] & G_group[1]);
    assign P_group[2] = P[2] & P_group[1];

    assign G_group[3] = G[3] | (P[3] & G_group[2]);
    assign P_group[3] = P[3] & P_group[2];

    // Compute carry-out C32 using the group generate and propagate
    assign C32 = G_group[3] | (P_group[3] & C_out[3]);

endmodule
