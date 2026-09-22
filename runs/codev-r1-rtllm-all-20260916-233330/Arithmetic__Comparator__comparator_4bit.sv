module comparator_4bit (
    input [3:0] A,
    input [3:0] B,
    output A_greater,
    output A_equal,
    output A_less
);

    // Perform subtraction A - B using 4-bit unsigned arithmetic
    wire [4:0] sub_result;
    assign sub_result = {1'b0, A} - {1'b0, B};

    // Determine the outputs based on subtraction result
    assign A_equal = (sub_result == 5'b0);
    assign A_less = sub_result[4]; // Borrow indicates A < B
    assign A_greater = (sub_result != 0) && !A_less && !A_equal;

endmodule
