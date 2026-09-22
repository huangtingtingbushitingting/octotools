module sequence_detector (
    input clk,
    input rst_n,
    input data_in,
    output reg sequence_detected
);

    // Define states
    typedef enum logic [2:0] {
        IDLE,
        S1,
        S2,
        S3,
        S4
    } state_t;

    state_t current_state, next_state;

    // State transition logic
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            current_state <= IDLE;
        end else begin
            current_state <= next_state;
        end
    end

    // Next state logic
    always @(*) begin
        case (current_state)
            IDLE: begin
                if (data_in == 1'b1) begin
                    next_state = S1;
                end else begin
                    next_state = IDLE;
                end
            end
            S1: begin
                if (data_in == 1'b0) begin
                    next_state = S2;
                end else begin
                    next_state = S1; // Stay in S1 if next bit is 1 (since sequence starts with 1)
                end
            end
            S2: begin
                if (data_in == 1'b0) begin
                    next_state = S3;
                end else begin
                    next_state = IDLE; // If bit is 1, reset to IDLE as sequence breaks
                end
            end
            S3: begin
                if (data_in == 1'b1) begin
                    next_state = S4;
                end else begin
                    next_state = IDLE; // If bit is 0, reset
                end
            end
            S4: begin
                if (data_in == 1'b1) begin
                    next_state = S1; // After detection, check if next bit starts new sequence
                end else begin
                    next_state = IDLE;
                end
            end
            default: next_state = IDLE;
        endcase
    end

    // Output logic
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sequence_detected <= 1'b0;
        end else begin
            sequence_detected <= (current_state == S4) && (data_in == 1'b1);
        end
    end

endmodule
