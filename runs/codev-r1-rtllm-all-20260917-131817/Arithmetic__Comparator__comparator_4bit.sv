module comparator_4bit (
    input [3:0] A,
    input [3:0] B,
    output A_greater,
    output A_equal,
    output A_less
);

    // Perform subtraction A - B
    wire [4:0] sub_result;
    assign sub_result = {1'b0, A} - {1'b0, B};

    // Determine the outputs based on subtraction result
    assign A_equal = (sub_result == 5'b00000);
    assign A_less = sub_result[4]; // Borrow occurred if MSB is 1
    assign A_greater = (sub_result != 5'b0) && !A_less && !A_equal;

endmodule
