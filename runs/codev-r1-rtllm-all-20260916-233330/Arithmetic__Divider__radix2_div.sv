module radix2_div (
    input clk,
    input rst,
    input sign,
    input [7:0] dividend,
    input [7:0] divisor,
    input opn_valid,
    input res_ready,
    output reg res_valid,
    output reg [15:0] result
);

    reg [7:0] abs_dividend;
    reg [7:0] abs_divisor;
    reg [7:0] neg_divisor;
    reg [7:0] quotient;
    reg [7:0] remainder;
    reg [3:0] cnt;
    reg start_cnt;
    reg [15:0] SR; // Shift register for remainder and quotient
    reg [7:0] saved_dividend;
    reg [7:0] saved_divisor;
    reg opn_valid_reg;

    // Internal signals
    wire [7:0] sub_result;
    wire carry_out;
    reg [7:0] temp_remainder;
    reg [7:0] temp_quotient;

    // Absolute values and sign handling
    always @* begin
        if (sign) begin
            abs_dividend = dividend[7] ? -dividend : dividend;
            abs_divisor = divisor[7] ? -divisor : divisor;
            neg_divisor = -abs_divisor;
        end else begin
            abs_dividend = dividend;
            abs_divisor = divisor;
            neg_divisor = -abs_divisor;
        end
    end

    // Shift register operations
    assign sub_result = SR[15:8] - neg_divisor;
    assign carry_out = (SR[15:8] >= neg_divisor) ? 1'b1 : 1'b0;

    // Main state machine
    always @(posedge clk) begin
        if (rst) begin
            res_valid <= 0;
            cnt <= 0;
            start_cnt <= 0;
            SR <= 0;
            quotient <= 0;
            remainder <= 0;
            saved_dividend <= 0;
            saved_divisor <= 0;
            opn_valid_reg <= 0;
            result <= 0;
        end else begin
            if (opn_valid && !res_valid && !opn_valid_reg) begin
                // Save inputs and initialize
                saved_dividend <= abs_dividend;
                saved_divisor <= abs_divisor;
                SR <= {abs_dividend, 8'b0}; // Initial shift register with dividend shifted left by 8 bits
                neg_divisor <= neg_divisor; // Already computed
                cnt <= 1;
                start_cnt <= 1;
                opn_valid_reg <= 1;
                res_valid <= 0;
            end else if (start_cnt) begin
                if (cnt == 8) begin
                    // Division complete
                    start_cnt <= 0;
                    cnt <= 0;
                    // Update remainder and quotient based on sign
                    if (sign) begin
                        remainder = (saved_dividend[7] ^ saved_divisor[7]) ? -SR[7:0] : SR[7:0];
                        quotient = (saved_dividend[7] ^ saved_divisor[7]) ? -quotient : quotient;
                    end else begin
                        remainder = SR[7:0];
                        quotient = quotient;
                    end
                    result <= {remainder, quotient};
                    res_valid <= 1;
                end else begin
                    // Perform subtraction and shift
                    if (carry_out) begin
                        SR <= {sub_result, SR[7:0], 1'b1};
                    end else begin
                        SR <= {SR[15:8] - neg_divisor, SR[7:0], 1'b0};
                    end
                    cnt <= cnt + 1;
                end
            end

            if (res_valid && res_ready) begin
                res_valid <= 0;
                opn_valid_reg <= 0;
            end
        end
    end

endmodule
