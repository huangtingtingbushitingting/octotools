module pulse_detect (
    input clk,
    input rst_n,
    input data_in,
    output reg data_out
);

    // Define states for the state machine
    localparam IDLE = 2'b00;
    localparam DETECT_1 = 2'b01;
    localparam DETECT_2 = 2'b10;
    localparam PULSE_END = 2'b11;

    reg [1:0] state, next_state;

    // State transition and state register
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
        end else begin
            state <= next_state;
        end
    end

    // Next state logic
    always @(*) begin
        case (state)
            IDLE: begin
                if (data_in) begin
                    next_state = DETECT_1;
                end else begin
                    next_state = IDLE;
                end
            end
            DETECT_1: begin
                if (data_in == 0) begin
                    next_state = DETECT_2;
                end else begin
                    next_state = DETECT_1;
                end
            end
            DETECT_2: begin
                if (data_in == 1) begin
                    next_state = PULSE_END;
                end else begin
                    next_state = DETECT_2;
                end
            end
            PULSE_END: begin
                if (data_in == 0) begin
                    next_state = IDLE;
                end else begin
                    next_state = PULSE_END;
                end
            end
            default: next_state = IDLE;
        endcase
    end

    // Output logic
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_out <= 0;
        end else begin
            case (state)
                PULSE_END: data_out <= 1;
                default: data_out <= 0;
            endcase
        end
    end

endmodule
