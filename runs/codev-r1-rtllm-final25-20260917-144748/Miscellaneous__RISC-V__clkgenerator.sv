module clkgenerator #(
    parameter PERIOD = 10
) (
    output reg clk = 0
);

    initial clk = 0;

    always #((PERIOD/2)*1000) clk = ~clk;

endmodule
