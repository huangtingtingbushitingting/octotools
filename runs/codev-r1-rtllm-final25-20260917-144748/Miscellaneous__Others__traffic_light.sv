module traffic_light (
    input rst_n,
    input clk,
    input pass_request,
    output reg [7:0] clock,
    output reg red,
    output reg yellow,
    output reg green
);

    // Parameters for states
    parameter idle = 2'b00;
    parameter s1_red = 2'b01;
    parameter s2_yellow = 2'b10;
    parameter s3_green = 2'b11;

    // Internal registers
    reg [7:0] cnt;
    reg [1:0] state;
    reg p_red, p_yellow, p_green;

    // State transition logic
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= idle;
        end else begin
            case (state)
                idle: begin
                    state <= s1_red;
                end
                s1_red: begin
                    if (cnt == 0) begin
                        state <= s3_green;
                    end
                end
                s3_green: begin
                    if (cnt == 0) begin
                        state <= s2_yellow;
                    end
                end
                s2_yellow: begin
                    if (cnt == 0) begin
                        state <= s1_red;
                    end
                end
                default: state <= idle;
            endcase
        end
    end

    // Counter logic
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cnt <= 10;
        end else begin
            if (pass_request && green && (cnt > 10)) begin
                cnt <= 10;
            end else begin
                case (state)
                    s1_red: begin
                        if (cnt == 0) begin
                            cnt <= 60;
                        end else begin
                            cnt <= cnt - 1;
                        end
                    end
                    s3_green: begin
                        if (cnt == 0) begin
                            cnt <= 5;
                        end else begin
                            cnt <= cnt - 1;
                        end
                    end
                    s2_yellow: begin
                        if (cnt == 0) begin
                            cnt <= 10;
                        end else begin
                            cnt <= cnt - 1;
                        end
                    end
                    default: cnt <= cnt - 1;
                endcase
            end
        end
    end

    // Output assignments
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            p_red <= 0;
            p_yellow <= 0;
            p_green <= 0;
        end else begin
            p_red <= red;
            p_yellow <= yellow;
            p_green <= green;
        end
    end

    // Next state logic for outputs
    always @(*) begin
        case (state)
            idle: begin
                red = 0;
                yellow = 0;
                green = 0;
            end
            s1_red: begin
                red = 1;
                yellow = 0;
                green = 0;
            end
            s2_yellow: begin
                red = 0;
                yellow = 1;
                green = 0;
            end
            s3_green: begin
                red = 0;
                yellow = 0;
                green = 1;
            end
            default: begin
                red = 0;
                yellow = 0;
                green = 0;
            end
        endcase
    end

    // Assign clock output
    assign clock = cnt;

endmodule
