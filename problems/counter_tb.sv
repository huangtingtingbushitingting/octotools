`timescale 1ns/1ps

module tb;
    reg a;
    reg b;
    reg sel;
    wire y;

    TopModule dut (
        .a(a),
        .b(b),
        .sel(sel),
        .y(y)
    );

    task check;
        input expected;
        begin
            #1;
            if (y !== expected) begin
                $display(
                    "FAIL: a=%b b=%b sel=%b y=%b expected=%b",
                    a, b, sel, y, expected
                );
                $fatal(1);
            end
        end
    endtask

    initial begin
        a = 0; b = 0; sel = 0; check(0);
        a = 1; b = 0; sel = 0; check(1);
        a = 0; b = 1; sel = 1; check(1);
        a = 1; b = 0; sel = 1; check(0);

        $display("PASS");
        $finish;
    end
endmodule