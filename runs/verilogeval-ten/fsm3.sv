module moore_fsm (
    input logic clk,
    input logic rst_n,
    input logic in,
    output logic out
);

    typedef enum logic [1:0] {
        A = 2'b00,
        B = 2'b01,
        C = 2'b10,
        D = 2'b11
    } state_t;

    state_t current_state, next_state;

    always_ff @(posedge clk, negedge rst_n) begin
        if (!rst_n)
            current_state <= A;
        else
            current_state <= next_state;
    end

    always_comb begin
        case (current_state)
            A: begin
                next_state = (in == 0) ? A : B;
                out = 0;
            end
            B: begin
                next_state = (in == 0) ? C : B;
                out = 0;
            end
            C: begin
                next_state = (in == 0) ? A : D;
                out = 0;
            end
            D: begin
                next_state = (in == 0) ? C : B;
                out = 1;
            end
        endcase
    end

endmodule
