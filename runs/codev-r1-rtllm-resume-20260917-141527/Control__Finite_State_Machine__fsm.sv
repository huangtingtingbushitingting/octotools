module fsm (
    input IN,
    input CLK,
    input RST,
    output reg MATCH
);

    // Define states for the FSM
    // The sequence to detect is 1 -> 0 -> 0 -> 1 -> 1
    // States represent the progress in the sequence
    // S0: Initial state, no bits matched
    // S1: First bit (1) matched
    // S2: Second bit (0) matched after S1
    // S3: Third bit (0) matched after S2
    // S4: Fourth bit (1) matched after S3
    // S5: Fifth bit (1) matched after S4 (this is the final state where MATCH is set)
    // S6: After detecting the sequence, but need to handle continuous input

    reg [2:0] state, next_state;

    parameter S0 = 3'd0,
              S1 = 3'd1,
              S2 = 3'd2,
              S3 = 3'd3,
              S4 = 3'd4,
              S5 = 3'd5;

    // State transition and output logic
    always @(posedge CLK or posedge RST) begin
        if (RST) begin
            state <= S0;
            MATCH <= 1'b0;
        end
        else begin
            state <= next_state;
            // Output logic: MATCH is 1 only when transitioning to S5
            MATCH <= (next_state == S5) ? 1'b1 : 1'b0;
        end
    end

    // Next state logic
    always @(*) begin
        case (state)
            S0: begin
                if (IN == 1'b1)
                    next_state = S1;
                else
                    next_state = S0;
            end
            S1: begin
                if (IN == 1'b0)
                    next_state = S2;
                else
                    next_state = S0; // Reset if input doesn't match
            end
            S2: begin
                if (IN == 1'b0)
                    next_state = S3;
                else
                    next_state = S0; // Reset if input doesn't match
            end
            S3: begin
                if (IN == 1'b1)
                    next_state = S4;
                else
                    next_state = S0; // Reset if input doesn't match
            end
            S4: begin
                if (IN == 1'b1)
                    next_state = S5;
                else
                    next_state = S0; // Reset if input doesn't match
            end
            S5: begin
                // After matching, reset to S0 if input doesn't start new sequence
                if (IN == 1'b1)
                    next_state = S1; // Possible start of new sequence
                else
                    next_state = S0;
            end
            default: next_state = S0;
        endcase
    end

endmodule
