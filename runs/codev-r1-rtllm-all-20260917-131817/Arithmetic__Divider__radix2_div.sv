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
    reg [7:0] SR; // Shift register
    reg [3:0] cnt;
    reg start_cnt;
    reg opn_valid_reg;
    reg res_ready_reg;
    reg sign_reg;

    // State management
    reg [1:0] state;
    localparam IDLE = 2'b00;
    localparam CALC = 2'b01;
    localparam DONE = 2'b10;

    // Temporary variables
    reg [7:0] temp_sub;
    reg carry_out;

    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE;
            res_valid <= 0;
            result <= 0;
            cnt <= 0;
            start_cnt <= 0;
            SR <= 0;
            quotient <= 0;
            remainder <= 0;
            abs_dividend <= 0;
            abs_divisor <= 0;
            neg_divisor <= 0;
            sign_reg <= 0;
            opn_valid_reg <= 0;
            res_ready_reg <= 0;
        end else begin
            res_ready_reg <= res_ready;
            opn_valid_reg <= opn_valid;

            case (state)
                IDLE: begin
                    if (opn_valid && !res_valid) begin
                        // Save inputs and compute absolute values if signed
                        sign_reg <= sign;
                        if (sign) begin
                            abs_dividend <= dividend[7] ? -dividend : dividend;
                            abs_divisor <= divisor[7] ? -divisor : divisor;
                            neg_divisor <= divisor[7] ? -divisor : divisor;
                        end else begin
                            abs_dividend <= dividend;
                            abs_divisor <= divisor;
                            neg_divisor <= divisor;
                        end
                        // Initialize shift register with absolute dividend shifted left by 1
                        SR <= {abs_dividend, 1'b0};
                        cnt <= 1;
                        start_cnt <= 1;
                        state <= CALC;
                    end
                end

                CALC: begin
                    if (start_cnt) begin
                        if (cnt == 8) begin
                            // Division complete
                            start_cnt <= 0;
                            cnt <= 0;
                            // Restore signs if needed
                            if (sign_reg) begin
                                quotient <= remainder[7] ? -quotient : quotient;
                                remainder <= remainder[7] ? -remainder : remainder;
                            end
                            // Update result
                            result <= {remainder, quotient};
                            res_valid <= 1;
                            state <= DONE;
                        end else begin
                            // Perform subtraction
                            temp_sub = SR[15:8] - neg_divisor;
                            carry_out = ~temp_sub[8]; // Check if subtraction is possible (no borrow)
                            // Update shift register
                            SR <= {temp_sub[7:0], SR[15:8], carry_out};
                            quotient <= {quotient[6:0], carry_out};
                            remainder <= temp_sub[7:0];
                            cnt <= cnt + 1;
                        end
                    end
                end

                DONE: begin
                    if (res_ready) begin
                        res_valid <= 0;
                        state <= IDLE;
                    end
                end

                default: state <= IDLE;
            endcase
        end
    end

endmodule
