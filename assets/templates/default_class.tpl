class %CLASS_EXPORT% %CLASS_NAME% {
public:
    // Constructor:
    %CLASS_NAME%();
    
    // Copy constructors:
    %CLASS_NAME%(const %CLASS_NAME%&) = default;
    auto operator=(const %CLASS_NAME%&) -> %CLASS_NAME%& = default;

    // Move constructors:
    %CLASS_NAME%(%CLASS_NAME%&&) = delete;
    auto operator=(%CLASS_NAME%&&) -> %CLASS_NAME%& = delete;

    // Destructor
    virtual ~%CLASS_NAME%() = default;
};
